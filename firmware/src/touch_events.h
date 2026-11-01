#pragma once
#include <esp_timer.h>
#include "pressure_calibration.h"
#include "expansion_inputs.h"
static bool sensorEnabled=false,resumeInputs=false;
static int sensorOn=1200,sensorOff=800;
#include "channel_devices.h"
static ContactInput contacts[MAX_CHANNELS];
static void refreshExpansionInputs(){for(const auto &c:channels)if(c.configured&&c.driver==ChannelDriver::GPIO_SWITCH)pinMode(c.gpio,INPUT);}
static void stopDigitalInputs(){for(auto &c:contacts)c=ContactInput();}
static void disarmOutputs(){} // Compatibility hook used by OTA; this build has no outputs.
static void initOutputPins(){}
static String touchBoot;
static uint32_t touchSeq=0;
static constexpr int TOUCH_CAP=128;
struct TouchRecord {
 uint32_t seq=0,touch=0;
 uint64_t at=0,duration=0,wall=0;
 int channel=0,raw=0,peak=0,mv=-1;
 float value=0;
 bool valid=true;
 DeviceKind kind=DeviceKind::PRESSURE;
 String body,phase,source,driver,quality;
};
static TouchRecord touchQueue[TOUCH_CAP];
struct TouchState {
 bool active=false,simulated=true;
 uint32_t id=0;
 uint64_t started=0,deadline=0;
 int raw=0,peak=0;
 String body,driver;
};
static TouchState touches[MAX_CHANNELS];
static int sensorRaw[MAX_CHANNELS]={};
static uint8_t sensorDebounce[MAX_CHANNELS]={};
struct PressureCalibration {
 int channel=-1,stage=-1;
 bool engaged=false,capturing=false,applied=false;
 uint64_t deadline=0,expires=0;
 PressureSamples stages[3];
 String error;
 void reset(){channel=-1;stage=-1;engaged=false;capturing=false;applied=false;deadline=expires=0;error="";for(auto &s:stages)s.reset();}
};
static PressureCalibration calibration;
static uint64_t touchNow(){return esp_timer_get_time()/1000ULL;}
static void encodeTouchRecord(JsonObject e,const TouchRecord &r,const String &boot){
 e["seq"]=r.seq;e["event_id"]=boot+"-"+String(r.seq);
 if(r.kind==DeviceKind::PRESSURE)e["touch_id"]=boot+"-"+String(r.touch);
 e["uptime_ms"]=r.at;e["phase"]=r.phase;e["channel"]=r.channel;e["body_part"]=r.body;
 e["sensor_type"]=kindName(r.kind);e["direction"]=outputKind(r.kind)?"output":"input";
 e["driver"]=r.driver;e["unit"]=unitName(r.kind);e["quality"]=r.quality;
 if(r.valid)e["value"]=r.value;else e["value"]=nullptr;
 if(r.mv>=0)e["adc_mv"]=r.mv;else e["adc_mv"]=nullptr;
 e["raw"]=r.raw;e["peak_raw"]=r.peak;e["duration_ms"]=r.duration;e["source"]=r.source;
 e["time_quality"]=r.wall?"device_clock":"unknown";
 if(r.wall)e["device_time_ms"]=r.wall;else e["device_time_ms"]=nullptr;
}
#include "event_storage.h"
static TouchRecord &newRecord(int ch,const String &phase){
 uint32_t seq=++touchSeq;TouchRecord &r=touchQueue[(seq-1)%TOUCH_CAP];r=TouchRecord();
 r.seq=seq;r.at=touchNow();r.wall=deviceWallTime();r.channel=ch;r.body=channels[ch].name;r.kind=channels[ch].kind;
 r.phase=phase;r.driver=driverName(channels[ch].driver);r.quality="ok";return r;
}
static void touchEmit(int ch,bool ended){
 TouchState &s=touches[ch];TouchRecord &r=newRecord(ch,ended?"end":"start");
 r.kind=DeviceKind::PRESSURE;r.touch=s.id;r.duration=r.at-s.started;r.body=s.body;r.driver=s.driver;
 r.raw=ended?0:s.raw;r.peak=s.peak;r.value=r.raw;r.source=s.simulated?"simulation":"sensor";
 persistTouchRecord(r);
}
static void touchInject(int ch,int value,bool simulated=true){
 TouchState &s=touches[ch];auto &v=readings[ch];v.sampled=true;v.valid=true;v.value=value;v.raw=value;v.at=touchNow();v.source=simulated?"simulation":"sensor";v.fault="";
 if(value==0){if(s.active){touchEmit(ch,true);s.active=false;}return;}
 if(s.active){touchEmit(ch,true);s.active=false;}
 s.active=true;s.started=touchNow();s.deadline=s.started+5000;s.raw=value;s.peak=value;
 s.body=channels[ch].name;s.driver=driverName(channels[ch].driver);s.simulated=simulated;s.id=touchSeq+1;touchEmit(ch,false);
}
// Compatibility status reads the same simulated press state as event consumers.
static int activeSimulatedPressure(){
 int selected=-1;
 for(int ch=0;ch<MAX_CHANNELS;ch++){
  const auto &s=touches[ch];
  if(!s.active||!s.simulated||channels[ch].kind!=DeviceKind::PRESSURE)continue;
  if(selected<0||(int32_t)(s.id-touches[selected].id)>0)selected=ch;
 }
 return selected;
}
static void applyInputEnabled(bool enabled){
 stopDigitalInputs();
 for(int i=0;i<MAX_CHANNELS;i++){if(touches[i].active&&!touches[i].simulated)touchInject(i,0,false);sensorDebounce[i]=0;}
 sensorEnabled=enabled;
 if(enabled){pinMode(3,OUTPUT);pinMode(4,OUTPUT);pinMode(5,OUTPUT);analogReadResolution(12);analogSetPinAttenuation(0,ADC_11db);analogSetPinAttenuation(1,ADC_11db);}
 else{pinMode(3,INPUT);pinMode(4,INPUT);pinMode(5,INPUT);calibration.engaged=false;calibration.capturing=false;}
 refreshExpansionInputs();
}
static bool persistChannels(const ChannelConfig *next,String &error,bool restore=resumeInputs){
 JsonDocument d;encodeChannels(d.to<JsonObject>(),next);
 d["resume_inputs"]=restore;d["retired_channels"]=serialized(retiredChannels);
 String payload=encode(d);
 // NVS strings are limited to 4000 bytes; expanded configurations use an atomic blob.
 if(prefs.putBytes("chcfg_blob",payload.c_str(),payload.length())!=payload.length()){error="Unable to save channel configuration";return false;}return true;
}
static __attribute__((noinline)) bool saveChannels(JsonVariantConst a,String &error){
 ChannelConfig next[MAX_CHANNELS];if(!parseChannels(a,next,error))return false;
 bool explicitModes=true,resume=false;
 for(JsonObjectConst p:a["channels"].as<JsonArrayConst>())if(p["mode"].isNull())explicitModes=false;
 if(explicitModes)for(const auto &c:next)if(physicalChannel(c))resume=true;
 if(!persistChannels(next,error,resume))return false;
 // Close events with their old names/types before applying new configuration.
 for(int i=0;i<MAX_CHANNELS;i++)if(touches[i].active)touchInject(i,0);
 disarmOutputs();stopDigitalInputs();sensorEnabled=false;resumeInputs=false;calibration.reset();
 for(int i=0;i<MAX_CHANNELS;i++){
  channels[i]=next[i];readings[i]=ChannelReading();sensorRaw[i]=0;sensorDebounce[i]=0;
 }
 pinMode(3,INPUT);pinMode(4,INPUT);pinMode(5,INPUT);initOutputPins();resumeInputs=resume;if(resume)applyInputEnabled(true);return true;
}
static __attribute__((noinline)) bool setChannelState(JsonVariantConst a,String &error){
 if(!a["channel"].is<int>()){error="channel integer required";return false;}
 int ch=a["channel"];if(ch<0||ch>=MAX_CHANNELS||!channels[ch].configured||outputKind(channels[ch].kind)){error="Choose a configured input channel";return false;}
 if(calibration.engaged){error="Finish or cancel calibration before changing ports";return false;}
 ChannelConfig next[MAX_CHANNELS];for(int i=0;i<MAX_CHANNELS;i++)next[i]=channels[i];
 if(!a["name"].isNull()){
  if(!a["name"].is<String>()||a["name"].as<String>().isEmpty()||a["name"].as<String>().length()>96){error="name must contain 1..96 UTF-8 bytes";return false;}
  next[ch].name=a["name"].as<String>();
 }
 if(!a["mode"].isNull()){
  String mode=a["mode"].as<String>();if(mode!="off"&&mode!="simulation"&&mode!="connected"){error="mode must be off, simulation or connected";return false;}
  if(mode=="connected"&&next[ch].driver==ChannelDriver::SIMULATION){error="Physical binding required; configure the driver first";return false;}
  next[ch].enabled=mode!="off";next[ch].simulate=mode=="simulation";
 }
 if(a["name"].isNull()&&a["mode"].isNull()){error="Provide name or mode";return false;}
 bool modeRequested=!a["mode"].isNull();
 bool changed=strcmp(channelMode(channels[ch]),channelMode(next[ch]))!=0;
 bool resume=resumeInputs;if(modeRequested){resume=false;for(const auto &c:next)if(physicalChannel(c))resume=true;}
 if(!persistChannels(next,error,resume))return false;
 // End only this port's old event before changing its label/source. Other
 // channels, calibration thresholds and GPIO bindings remain intact.
 if(changed&&touches[ch].active)touchInject(ch,0);
 channels[ch]=next[ch];if(changed){readings[ch]=ChannelReading();sensorDebounce[ch]=0;contacts[ch]=ContactInput();}resumeInputs=resume;
 if(modeRequested&&sensorEnabled!=resume)applyInputEnabled(resume);
 refreshExpansionInputs();
 return true;
}
static void touchInit(){
 touchBoot=randomHex();JsonDocument names;deserializeJson(names,prefs.getString("bodymap","[]"));
 for(int i=0;i<8;i++){channels[i].configured=true;channels[i].mux=i;channels[i].name=names[i].is<String>()?names[i].as<String>():"CH"+String(i);}
 JsonDocument stored;String saved=prefs.getString("channels","{}");
 size_t bytes=prefs.isKey("chcfg_blob")?prefs.getBytesLength("chcfg_blob"):0;
 if(bytes&&bytes<=16384){char* data=(char*)malloc(bytes+1);if(data){if(prefs.getBytes("chcfg_blob",data,bytes)==bytes){data[bytes]=0;saved=String(data);}free(data);}}
 if(!deserializeJson(stored,saved)&&stored["channels"].is<JsonArray>()){
  retireUnsupportedChannels(stored);
  JsonDocument retired;deserializeJson(retired,retiredChannels);for(JsonVariantConst row:retired.as<JsonArrayConst>())if(row["driver"]=="gpio_pwm"){int pin=row["gpio"]|-1;if(pin==6||pin==7||pin==10||pin==20){digitalWrite(pin,LOW);pinMode(pin,OUTPUT);}}
  ChannelConfig next[MAX_CHANNELS];String error;if(stored["channels"].size()==0||parseChannels(stored.as<JsonVariantConst>(),next,error)){
   for(int i=0;i<MAX_CHANNELS;i++)channels[i]=next[i];
   resumeInputs=stored["resume_inputs"].is<bool>()&&stored["resume_inputs"].as<bool>();
  }
 }
 // Only a genuinely blank installation gets the physical CH0 default.
 // Older manual/calibrated configurations, including invalid saved data, remain untouched.
 if(!prefs.isKey("token")&&!prefs.isKey("channels")&&!prefs.isKey("chcfg_blob")){
  for(int i=0;i<8;i++)channels[i].enabled=(i==0);
  resumeInputs=true;String error;
  if(!persistChannels(channels,error,true))resumeInputs=false;
 }
 // No actuator can resume automatically after reboot.
 initOutputPins();
 if(resumeInputs)applyInputEnabled(true);
}
static void bodyMap(JsonObject out){
 JsonArray a=out["parts"].to<JsonArray>();for(int i=0;i<MAX_CHANNELS;i++)if(channels[i].configured){JsonObject p=a.add<JsonObject>();p["channel"]=i;p["name"]=channels[i].name;}
}
static __attribute__((noinline)) bool saveBodyMap(JsonVariantConst a,String &error){
 if(!a["parts"].is<JsonArrayConst>()||a["parts"].size()!=channelCount()){error="Provide names for all configured channels";return false;}
 ChannelConfig next[MAX_CHANNELS];for(int i=0;i<MAX_CHANNELS;i++)next[i]=channels[i];bool seen[MAX_CHANNELS]={};
 for(JsonObjectConst p:a["parts"].as<JsonArrayConst>()){
  if(!p["channel"].is<int>()||!p["name"].is<String>()){error="Invalid channel/name";return false;}
  int ch=p["channel"];String name=p["name"].as<String>();
  if(ch<0||ch>=MAX_CHANNELS||!channels[ch].configured||seen[ch]||name.isEmpty()||name.length()>96){error="Unique configured channel IDs and names 1..96 UTF-8 bytes required";return false;}
  seen[ch]=true;next[ch].name=name;
 }
 if(!persistChannels(next,error))return false;
 for(int i=0;i<MAX_CHANNELS;i++)channels[i].name=next[i].name;
 return true;
}
static void readChannels(JsonObject out){
 out["physical_inputs_enabled"]=sensorEnabled;out["physical_outputs_enabled"]=outputEnabled;
 JsonArray a=out["values"].to<JsonArray>();uint64_t now=touchNow();
 for(int ch=0;ch<MAX_CHANNELS;ch++)if(channels[ch].configured){
  auto &c=channels[ch];auto &s=readings[ch];JsonObject p=a.add<JsonObject>();p["channel"]=ch;p["name"]=c.name;p["type"]=kindName(c.kind);p["direction"]=outputKind(c.kind)?"output":"input";p["driver"]=driverName(c.driver);p["mode"]=channelMode(c);p["unit"]=unitName(c.kind);p["source"]=s.source;p["uptime_ms"]=s.at;
  String quality=!c.enabled?"disabled":!s.sampled?"not_sampled":(s.source=="sensor"&&!sensorEnabled)?"inputs_disabled":!s.valid?s.fault:((s.source=="sensor"&&now-s.at>max(5000,c.sampleMs*3))?"stale":"ok");p["quality"]=quality;
  if(quality=="ok")p["value"]=s.value;else p["value"]=nullptr;
  p["raw"]=s.raw;if(s.mv>=0)p["adc_mv"]=s.mv;else p["adc_mv"]=nullptr;
  if(c.kind==DeviceKind::SWITCH)p["active"]=s.value>=0.5f;
  if(c.kind==DeviceKind::PRESSURE){p["active"]=touches[ch].active;p["press_threshold"]=c.on;p["release_threshold"]=c.off;p["calibrating"]=calibration.engaged&&calibration.channel==ch;}
 }
}
static void expansionRecord(int ch,const String &phase,float value,const String &source,bool valid=true,const String &fault=""){
 auto &v=readings[ch];v.sampled=true;v.valid=valid;v.value=value;v.at=touchNow();v.source=source;v.fault=fault;
 auto &r=newRecord(ch,phase);r.value=value;r.valid=valid;r.source=source;r.quality=valid?"ok":fault;
 persistTouchRecord(r);
}
static bool simulateInput(JsonVariantConst a,String &error){
 if(!a["channel"].is<int>()||!a["value"].is<float>()){error="channel and numeric value required";return false;}
 int ch=a["channel"];float value=a["value"];
 if(!validChannel(ch)||outputKind(channels[ch].kind)){error="Choose an enabled input channel";return false;}
 if(!channels[ch].simulate&&channels[ch].driver!=ChannelDriver::SIMULATION){error="Set this port to simulation before injecting; other physical ports may keep sampling";return false;}
 if(!isfinite(value)){error="Finite value required";return false;}
 if(!a["unit"].isNull()&&!a["unit"].is<String>()){error="unit must be a string";return false;}
 String unit=a["unit"].is<String>()?a["unit"].as<String>():String(unitName(channels[ch].kind));
 if(channels[ch].kind==DeviceKind::PRESSURE){
  if(unit!="adc_raw"||value<0||value>4095||floorf(value)!=value){error="Pressure: adc_raw integer 0..4095";return false;}
  touchInject(ch,(int)value);
 }else if(channels[ch].kind==DeviceKind::SWITCH){
  if(unit!="boolean"||(value!=0&&value!=1)){error="Switch: boolean value 0 or1";return false;}
  expansionRecord(ch,value?"close":"open",value,"simulation");
 }else{error="Only pressure and switch simulation are supported";return false;}
 return true;
}
static void sensorConfig(JsonObject out){
 out["enabled"]=sensorEnabled;out["press_threshold"]=sensorOn;out["release_threshold"]=sensorOff;out["adc_gpio"]=0;out["mux_select_gpio"]="3,4,5";
 JsonArray a=out["raw"].to<JsonArray>();for(int i=0;i<MAX_CHANNELS;i++)if(channels[i].configured)a.add(sensorRaw[i]);
}
static bool setSensors(JsonVariantConst a,String &error){
 if(!a["enabled"].is<bool>()||!a["press_threshold"].is<int>()||!a["release_threshold"].is<int>()){error="enabled and integer thresholds required";return false;}
 int on=a["press_threshold"],off=a["release_threshold"];if(off<0||on>4095||on<=off){error="0 <= release_threshold < press_threshold <= 4095";return false;}
 applyInputEnabled(a["enabled"]);calibration.reset();sensorOn=on;sensorOff=off;
 // Legacy threshold settings are session overrides; channel thresholds persist separately.
 for(auto &c:channels)if(c.kind==DeviceKind::PRESSURE){c.on=on;c.off=off;}
 return true;
}
static bool setInputEnabled(JsonVariantConst a,String &error){
 if(!a["enabled"].is<bool>()){error="enabled boolean required";return false;}
 applyInputEnabled(a["enabled"]);return true;
}
static void operatingMode(JsonObject out){
 out["mode"]=resumeInputs?"daily":"manual";out["resume_inputs_after_reboot"]=resumeInputs;
 out["physical_inputs_enabled"]=sensorEnabled;out["physical_outputs_enabled"]=outputEnabled;
 out["outputs_resume_after_reboot"]=false;
}
static bool setOperatingMode(JsonVariantConst a,String &error){
 if(!a["mode"].is<String>()||(a["mode"]!="daily"&&a["mode"]!="manual")){error="mode must be daily or manual";return false;}
 bool daily=a["mode"]=="daily";
 if(daily&&(!a["hardware_confirmed"].is<bool>()||!a["hardware_confirmed"].as<bool>())){error="Confirm assembled sensor hardware before daily mode";return false;}
 if(daily){bool physical=false;for(auto &c:channels)if(c.configured&&c.enabled&&!outputKind(c.kind)&&c.driver!=ChannelDriver::SIMULATION)physical=true;
  if(!physical){error="Daily mode requires an enabled physical input";return false;}}
 if(!persistChannels(channels,error,daily))return false;
 resumeInputs=daily;disarmOutputs();applyInputEnabled(daily);return true;
}
static __attribute__((noinline)) void calibrationStatus(JsonObject out){
 out["channel"]=calibration.channel;out["capturing"]=calibration.capturing;out["engaged"]=calibration.engaged;out["applied"]=calibration.applied;
 out["source"]="sensor";out["stage"]=calibration.stage;out["error"]=calibration.error;
 uint64_t now=touchNow();out["remaining_ms"]=calibration.capturing&&calibration.deadline>now?calibration.deadline-now:0;
 JsonArray stages=out["stages"].to<JsonArray>();for(int i=0;i<3;i++){auto &s=calibration.stages[i];JsonObject v=stages.add<JsonObject>();v["stage"]=i;v["samples"]=s.count;v["p20"]=s.percentile(20);v["median"]=s.percentile(50);v["p95"]=s.percentile(95);}
 auto recommended=pressureThresholds(calibration.stages);out["ready"]=calibration.engaged&&!calibration.capturing&&recommended.valid;out["reason"]=recommended.reason;
 if(recommended.valid){out["press_threshold"]=recommended.on;out["release_threshold"]=recommended.off;}
}
static __attribute__((noinline)) bool captureCalibration(JsonVariantConst a,String &error){
 if(!a["channel"].is<int>()||!a["stage"].is<int>()||(!a["duration_ms"].isNull()&&!a["duration_ms"].is<int>())){error="channel/stage and optional duration_ms integers required";return false;}
 int ch=a["channel"],stage=a["stage"],duration=a["duration_ms"]|3000;
 if(!validChannel(ch)||channels[ch].kind!=DeviceKind::PRESSURE||!physicalChannel(channels[ch])||!sensorEnabled){error="Calibration requires connected physical pressure sampling";return false;}
 if(stage<0||stage>2||duration<500||duration>10000){error="stage 0..2; duration_ms 500..10000";return false;}
 if(calibration.capturing){error="Wait for current capture or cancel calibration";return false;}
 if(stage==0){calibration.reset();calibration.channel=ch;calibration.engaged=true;
  disarmOutputs();
  if(touches[ch].active)touchInject(ch,0);
  sensorDebounce[ch]=0;}
 else if(!calibration.engaged||calibration.channel!=ch||calibration.stages[stage-1].count<20){error="Capture idle, light and strong stages in order on one channel";return false;}
 for(int i=stage;i<3;i++)calibration.stages[i].reset();
 calibration.stage=stage;calibration.capturing=true;calibration.applied=false;calibration.error="";
 calibration.deadline=touchNow()+duration;calibration.expires=touchNow()+60000;return true;
}
static __attribute__((noinline)) bool applyCalibration(String &error){
 auto recommended=pressureThresholds(calibration.stages);
 if(!calibration.engaged||calibration.capturing||!recommended.valid){error=String("Calibration cannot be saved: ")+recommended.reason;return false;}
 ChannelConfig next[MAX_CHANNELS];for(int i=0;i<MAX_CHANNELS;i++)next[i]=channels[i];
 next[calibration.channel].on=recommended.on;next[calibration.channel].off=recommended.off;
 if(!persistChannels(next,error))return false;
 channels[calibration.channel]=next[calibration.channel];sensorDebounce[calibration.channel]=0;
 calibration.applied=true;calibration.engaged=false;return true;
}
static void touchTick(){
 uint64_t now=touchNow();
 if(calibration.capturing&&now>=calibration.deadline)calibration.capturing=false;
 if(calibration.engaged&&now>=calibration.expires){calibration.engaged=false;calibration.capturing=false;calibration.error="Calibration expired; start again";}
 for(int ch=0;ch<MAX_CHANNELS;ch++){
  if(touches[ch].active&&touches[ch].simulated&&now>=touches[ch].deadline)touchInject(ch,0);

 }
 static uint64_t sampled=0;if(!sensorEnabled||now-sampled<20)return;sampled=now;
 for(int ch=0;ch<MAX_CHANNELS;ch++){
  auto &c=channels[ch];auto &v=readings[ch];
  if(!physicalChannel(c))continue;
  if(c.driver==ChannelDriver::GPIO_SWITCH){
   bool value=(digitalRead(c.gpio)==LOW)==c.activeLow;bool initial=!contacts[ch].ready;
   bool changed=contacts[ch].sample(value,now,c.debounceMs);v.raw=digitalRead(c.gpio);v.value=contacts[ch].active;v.sampled=true;v.valid=true;v.source="sensor";v.fault="";v.at=now;
   if(changed||initial)expansionRecord(ch,initial?"sample":contacts[ch].active?"close":"open",v.value,"sensor");
   continue;
  }
  int gpio=c.driver==ChannelDriver::MUX_ADC?0:c.gpio;
  if(c.driver==ChannelDriver::MUX_ADC){digitalWrite(3,c.mux&1);digitalWrite(4,(c.mux>>1)&1);digitalWrite(5,(c.mux>>2)&1);delayMicroseconds(500);}
  analogRead(gpio);int sum=0;for(int j=0;j<4;j++)sum+=analogRead(gpio);int raw=sum/4;sensorRaw[ch]=raw;v.raw=raw;
  v.sampled=true;v.valid=true;v.value=raw;v.at=now;v.source="sensor";
  if(calibration.engaged&&calibration.channel==ch){if(calibration.capturing)calibration.stages[calibration.stage].add(raw);sensorDebounce[ch]=0;continue;}
  TouchState &s=touches[ch];bool transition=s.active?raw<=c.off:raw>=c.on;if(s.active){s.raw=raw;s.peak=max(s.peak,raw);}
  if(!transition){sensorDebounce[ch]=0;continue;}if(++sensorDebounce[ch]>=3){sensorDebounce[ch]=0;touchInject(ch,s.active?0:raw,false);}
 }
}
static void touchRead(JsonObject out,uint32_t after,const String &boot,bool includePersistent=false,const String &archiveLeaseId=""){
 uint32_t oldest=touchSeq>=TOUCH_CAP?touchSeq-TOUCH_CAP+1:1;bool reset=boot.length()&&boot!=touchBoot;if(reset)after=0;
 out["schema_version"]=3;out["boot_id"]=touchBoot;out["device_id"]=apName;out["uptime_ms"]=touchNow();out["boot_changed"]=reset;out["latest_seq"]=touchSeq;out["oldest_seq"]=oldest;
 out["gap"]=after<oldest-1;out["next_cursor"]=after;JsonArray events=out["events"].to<JsonArray>();
 if(includePersistent)readEventBacklog(out,archiveLeaseId);else eventStorageStatus(out["event_storage"].to<JsonObject>());
 size_t persistentCount=out["persistent_events"].size();
 for(uint32_t seq=max(after+1,oldest);seq<=touchSeq&&events.size()+persistentCount<24;seq++){
  TouchRecord &r=touchQueue[(seq-1)%TOUCH_CAP];encodeTouchRecord(events.add<JsonObject>(),r,touchBoot);out["next_cursor"]=seq;
 }
}
