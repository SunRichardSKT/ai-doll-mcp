#pragma once
#include <esp_timer.h>
#include "pressure_calibration.h"
static bool sensorEnabled=false;
static bool resumeInputs=false;
static int sensorOn=1200,sensorOff=800;
#include "channel_devices.h"

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
struct OutputState {
 bool active=false,physical=false;
 volatile bool expired=false;
 int intensity=0,pwm=-1;
 uint64_t started=0,deadline=0;
 esp_timer_handle_t timer=nullptr;
 String body,driver;
};
static OutputState outputs[MAX_CHANNELS];
static uint64_t touchNow(){return esp_timer_get_time()/1000ULL;}
static void encodeTouchRecord(JsonObject e,const TouchRecord &r,const String &boot){
 e["seq"]=r.seq;e["event_id"]=boot+"-"+String(r.seq);
 if(r.kind==DeviceKind::PRESSURE)e["touch_id"]=boot+"-"+String(r.touch);
 e["uptime_ms"]=r.at;e["phase"]=r.phase;e["channel"]=r.channel;e["body_part"]=r.body;
 e["sensor_type"]=kindName(r.kind);e["direction"]=r.kind==DeviceKind::VIBRATION?"output":"input";
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
static void motorDeadline(void* argument){
 auto *s=static_cast<OutputState*>(argument);
 // Runs in ESP timer task: stop PWM even if a slow HTTP client blocks the main loop.
 if(s->pwm>=0)ledcWrite(s->pwm,0);
 s->expired=true;
}
static void stopOutput(int ch,bool record=true){
 auto &s=outputs[ch];if(s.timer)esp_timer_stop(s.timer);
 if(s.physical&&s.pwm>=0)ledcWrite(s.pwm,0);
 if(s.active&&record){auto &r=newRecord(ch,"stop");r.body=s.body;r.driver=s.driver;r.source=s.physical?"actuator":"simulation";r.duration=r.at-s.started;r.value=0;persistTouchRecord(r);}
 s.active=false;s.intensity=0;s.expired=false;
 auto &v=readings[ch];v.value=0;v.valid=true;v.sampled=true;v.at=touchNow();v.source=s.physical?"actuator":"simulation";
}
static void disarmOutputs(){for(int ch=0;ch<MAX_CHANNELS;ch++)if(outputs[ch].active)stopOutput(ch);outputEnabled=false;}
static void initOutputPins(){
 for(int ch=0;ch<MAX_CHANNELS;ch++){
  auto &c=channels[ch];auto &s=outputs[ch];s.pwm=-1;s.physical=false;
  if(c.configured&&c.driver==ChannelDriver::GPIO_PWM){pinMode(c.gpio,OUTPUT);digitalWrite(c.gpio,LOW);s.pwm=c.gpio==6?0:c.gpio==7?1:2;}
 }
}
static void applyInputEnabled(bool enabled){
 for(int i=0;i<MAX_CHANNELS;i++){if(touches[i].active)touchInject(i,0);sensorDebounce[i]=0;}
 sensorEnabled=enabled;
 if(enabled){pinMode(3,OUTPUT);pinMode(4,OUTPUT);pinMode(5,OUTPUT);analogReadResolution(12);analogSetPinAttenuation(0,ADC_11db);analogSetPinAttenuation(1,ADC_11db);}
 else{pinMode(3,INPUT);pinMode(4,INPUT);pinMode(5,INPUT);calibration.engaged=false;calibration.capturing=false;}
}
static bool persistChannels(const ChannelConfig *next,String &error,bool restore=resumeInputs){
 JsonDocument d;encodeChannels(d.to<JsonObject>(),next);
 d["resume_inputs"]=restore;
 String payload=encode(d);
 // NVS strings are limited to 4000 bytes; expanded configurations use an atomic blob.
 if(prefs.putBytes("chcfg_blob",payload.c_str(),payload.length())!=payload.length()){error="Unable to save channel configuration";return false;}return true;
}
static __attribute__((noinline)) bool saveChannels(JsonVariantConst a,String &error){
 ChannelConfig next[MAX_CHANNELS];if(!parseChannels(a,next,error))return false;
 if(!persistChannels(next,error,false))return false;
 // Close events with their old names/types before applying new configuration.
 for(int i=0;i<MAX_CHANNELS;i++)if(touches[i].active)touchInject(i,0);
 disarmOutputs();sensorEnabled=false;resumeInputs=false;calibration.reset();pressChannel=-1;pressValue=0;
 for(int i=0;i<MAX_CHANNELS;i++){
  if(channels[i].configured&&channels[i].driver==ChannelDriver::GPIO_PWM){ledcDetachPin(channels[i].gpio);pinMode(channels[i].gpio,INPUT);}
  channels[i]=next[i];readings[i]=ChannelReading();sensorRaw[i]=0;sensorDebounce[i]=0;
 }
 pinMode(3,INPUT);pinMode(4,INPUT);pinMode(5,INPUT);initOutputPins();return true;
}
static void touchInit(){
 touchBoot=randomHex();JsonDocument names;deserializeJson(names,prefs.getString("bodymap","[]"));
 for(int i=0;i<8;i++){channels[i].configured=true;channels[i].mux=i;channels[i].name=names[i].is<String>()?names[i].as<String>():"CH"+String(i);}
 JsonDocument stored;String saved=prefs.getString("channels","{}");
 size_t bytes=prefs.isKey("chcfg_blob")?prefs.getBytesLength("chcfg_blob"):0;
 if(bytes&&bytes<=16384){char* data=(char*)malloc(bytes+1);if(data){if(prefs.getBytes("chcfg_blob",data,bytes)==bytes){data[bytes]=0;saved=String(data);}free(data);}}
 if(!deserializeJson(stored,saved)&&stored["channels"].is<JsonArray>()){
  ChannelConfig next[MAX_CHANNELS];String error;if(parseChannels(stored.as<JsonVariantConst>(),next,error)){
   for(int i=0;i<MAX_CHANNELS;i++)channels[i]=next[i];
   resumeInputs=stored["resume_inputs"].is<bool>()&&stored["resume_inputs"].as<bool>();
  }
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
  auto &c=channels[ch];auto &s=readings[ch];JsonObject p=a.add<JsonObject>();p["channel"]=ch;p["name"]=c.name;p["type"]=kindName(c.kind);p["direction"]=c.kind==DeviceKind::VIBRATION?"output":"input";p["driver"]=driverName(c.driver);p["unit"]=unitName(c.kind);p["source"]=s.source;p["uptime_ms"]=s.at;
  String quality=!c.enabled?"disabled":!s.sampled?"not_sampled":(s.source=="sensor"&&!sensorEnabled)?"inputs_disabled":!s.valid?s.fault:((s.source=="sensor"&&now-s.at>max(5000,c.sampleMs*3))?"stale":"ok");p["quality"]=quality;
  if(quality=="ok")p["value"]=s.value;else p["value"]=nullptr;
  p["raw"]=s.raw;if(s.mv>=0)p["adc_mv"]=s.mv;else p["adc_mv"]=nullptr;if(c.kind==DeviceKind::VIBRATION){p["active"]=outputs[ch].active;p["feedback"]="commanded_state_only";}
  if(c.kind==DeviceKind::PRESSURE){p["active"]=touches[ch].active;p["press_threshold"]=c.on;p["release_threshold"]=c.off;p["calibrating"]=calibration.engaged&&calibration.channel==ch;}
 }
}
static bool ntcValue(int ch,float mv,float &celsius,String &fault){
 const auto &c=channels[ch];if(mv<=10||mv>=c.vcc-10){fault="adc_out_of_range";return false;}
 float resistance=c.pullDown*(c.vcc/mv-1)-c.series;
 if(resistance<=0){fault="invalid_ntc_resistance";return false;}
 celsius=1/(1/298.15f+logf(resistance/c.r0)/c.beta)-273.15f+c.offset;
 if(!isfinite(celsius)||celsius< -40||celsius>125){fault="temperature_out_of_range";return false;}return true;
}
static void temperatureRecord(int ch,float value,bool valid,const String &source,const String &fault=""){
 auto &s=readings[ch];bool unchangedQuality=s.sampled&&s.valid==valid&&s.fault==fault;s.sampled=true;s.valid=valid;s.value=value;s.at=touchNow();s.source=source;s.fault=fault;
 if(source=="sensor"&&unchangedQuality&&s.lastReport&&s.at-s.lastReport<(uint64_t)channels[ch].reportMs&&(valid?fabsf(value-s.reported)<0.2f:true))return;
 auto &r=newRecord(ch,"sample");r.value=value;r.valid=valid;r.source=source;r.quality=valid?"ok":fault;r.raw=s.raw;r.mv=s.mv;
 persistTouchRecord(r);
 s.lastReport=s.at;s.reported=value;
}
static bool simulateInput(JsonVariantConst a,String &error){
 if(!a["channel"].is<int>()||!a["value"].is<float>()){error="channel and numeric value required";return false;}
 int ch=a["channel"];float value=a["value"];
 if(!validChannel(ch)||channels[ch].kind==DeviceKind::VIBRATION){error="Choose an enabled input channel";return false;}
 if(sensorEnabled&&channels[ch].driver!=ChannelDriver::SIMULATION){error="Disable physical sampling before injecting this channel";return false;}
 if(!isfinite(value)){error="Finite value required";return false;}
 if(!a["unit"].isNull()&&!a["unit"].is<String>()){error="unit must be a string";return false;}
 String unit=a["unit"].is<String>()?a["unit"].as<String>():String(unitName(channels[ch].kind));
 if(channels[ch].kind==DeviceKind::PRESSURE){
  if(unit!="adc_raw"||value<0||value>4095||floorf(value)!=value){error="Pressure: adc_raw integer 0..4095";return false;}
  touchInject(ch,(int)value);pressValue=value;pressChannel=value?ch:-1;pressUntil=millis()+5000;
 }else if(unit=="degC"){
  if(value< -40||value>125){error="Temperature: -40..125 degC";return false;}readings[ch].mv=-1;readings[ch].raw=0;temperatureRecord(ch,value,true,"simulation");
 }else if(unit=="millivolt"){
  if(value<0||value>channels[ch].vcc){error="millivolt must be 0..supply_mv";return false;}String fault;float temp=0;readings[ch].mv=lroundf(value);bool valid=ntcValue(ch,value,temp,fault);temperatureRecord(ch,temp,valid,"simulation",fault);
 }else{error="Temperature unit: degC or millivolt";return false;}
 return true;
}
static bool armOutputs(JsonVariantConst a,String &error){
 if(!a["enabled"].is<bool>()){error="enabled boolean required";return false;}
 if(!a["enabled"].as<bool>()){disarmOutputs();return true;}
 if(calibration.engaged){error="Finish or cancel calibration before enabling physical outputs";return false;}
 if(!a["external_driver_confirmed"].is<bool>()||!a["external_driver_confirmed"].as<bool>()){error="Confirm an external motor driver before enabling physical outputs";return false;}
 if(outputEnabled)return true;
 for(int ch=0;ch<MAX_CHANNELS;ch++)if(channels[ch].configured&&channels[ch].enabled&&channels[ch].driver==ChannelDriver::GPIO_PWM){
  int pwm=outputs[ch].pwm;if(!ledcSetup(pwm,200,8)){error="PWM setup failed";disarmOutputs();return false;}ledcAttachPin(channels[ch].gpio,pwm);ledcWrite(pwm,0);
 }
 outputEnabled=true;return true;
}
static bool vibrate(JsonVariantConst a,String &error){
 if(!a["channel"].is<int>()||!a["intensity"].is<int>()||!a["duration_ms"].is<int>()){error="channel/intensity/duration_ms integers required";return false;}
 int ch=a["channel"],intensity=a["intensity"],duration=a["duration_ms"];
 if(!validChannel(ch)||channels[ch].kind!=DeviceKind::VIBRATION||intensity<0||intensity>100||duration<1||duration>5000){error="Enabled vibration channel; intensity 0..100, duration 1..5000 ms";return false;}
 bool physical=channels[ch].driver==ChannelDriver::GPIO_PWM;
 if(physical&&intensity&&calibration.engaged){error="Physical vibration is disabled during calibration";return false;}
 if(physical&&!outputEnabled&&intensity){error="Physical outputs are disabled; confirm external driver and enable first";return false;}
 stopOutput(ch);auto &s=outputs[ch];s.physical=physical;
 if(!intensity)return true;
 if(physical&&!s.timer){esp_timer_create_args_t args={};args.callback=motorDeadline;args.arg=&s;args.name="doll-motor";if(esp_timer_create(&args,&s.timer)!=ESP_OK){error="Output timer unavailable";return false;}}
 s.started=touchNow();s.deadline=s.started+duration;s.intensity=intensity;s.active=true;s.expired=false;s.body=channels[ch].name;s.driver=driverName(channels[ch].driver);
 if(physical){ledcWrite(s.pwm,lroundf(intensity*255.0f/100));if(esp_timer_start_once(s.timer,duration*1000ULL)!=ESP_OK){stopOutput(ch,false);error="Output timer failed";return false;}}
 auto &v=readings[ch];v.sampled=true;v.valid=true;v.at=s.started;v.value=intensity;v.source=physical?"actuator":"simulation";
 auto &r=newRecord(ch,"output");r.value=intensity;r.source=v.source;r.duration=duration;persistTouchRecord(r);return true;
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
 if(daily){bool physical=false;for(auto &c:channels)if(c.configured&&c.enabled&&(c.driver==ChannelDriver::MUX_ADC||c.driver==ChannelDriver::GPIO_ADC))physical=true;
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
 if(!validChannel(ch)||channels[ch].kind!=DeviceKind::PRESSURE||channels[ch].driver==ChannelDriver::SIMULATION||!sensorEnabled){error="Calibration requires enabled physical pressure sampling";return false;}
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
  if(outputs[ch].active&&(outputs[ch].expired||now>=outputs[ch].deadline))stopOutput(ch);
 }
 static uint64_t sampled=0;if(!sensorEnabled||now-sampled<20)return;sampled=now;
 for(int ch=0;ch<MAX_CHANNELS;ch++){
  auto &c=channels[ch];auto &v=readings[ch];
  if(!c.configured||!c.enabled||c.kind==DeviceKind::VIBRATION||c.driver==ChannelDriver::SIMULATION)continue;
  if(c.kind==DeviceKind::TEMPERATURE&&now-v.lastSample<(uint64_t)c.sampleMs)continue;
  v.lastSample=now;
  int gpio=c.driver==ChannelDriver::MUX_ADC?0:c.gpio;
  if(c.driver==ChannelDriver::MUX_ADC){digitalWrite(3,c.mux&1);digitalWrite(4,(c.mux>>1)&1);digitalWrite(5,(c.mux>>2)&1);delayMicroseconds(500);}
  analogRead(gpio);int sum=0;for(int j=0;j<4;j++)sum+=analogRead(gpio);int raw=sum/4;sensorRaw[ch]=raw;v.raw=raw;
  if(c.kind==DeviceKind::TEMPERATURE){
   uint32_t mv=0;for(int j=0;j<4;j++)mv+=analogReadMilliVolts(gpio);v.mv=mv/4;
   float value=0;String fault;bool valid=ntcValue(ch,v.mv,value,fault);if(raw<=5||raw>=4090){valid=false;fault="adc_saturated";}temperatureRecord(ch,value,valid,"sensor",fault);continue;
  }
  v.sampled=true;v.valid=true;v.value=raw;v.at=now;v.source="sensor";
  if(calibration.engaged&&calibration.channel==ch){if(calibration.capturing)calibration.stages[calibration.stage].add(raw);sensorDebounce[ch]=0;continue;}
  TouchState &s=touches[ch];bool transition=s.active?raw<=c.off:raw>=c.on;if(s.active){s.raw=raw;s.peak=max(s.peak,raw);}
  if(!transition){sensorDebounce[ch]=0;continue;}if(++sensorDebounce[ch]>=3){sensorDebounce[ch]=0;touchInject(ch,s.active?0:raw,false);}
 }
}
static void touchRead(JsonObject out,uint32_t after,const String &boot,bool includePersistent=false){
 uint32_t oldest=touchSeq>=TOUCH_CAP?touchSeq-TOUCH_CAP+1:1;bool reset=boot.length()&&boot!=touchBoot;if(reset)after=0;
 out["schema_version"]=3;out["boot_id"]=touchBoot;out["device_id"]=apName;out["uptime_ms"]=touchNow();out["boot_changed"]=reset;out["latest_seq"]=touchSeq;out["oldest_seq"]=oldest;
 out["gap"]=after<oldest-1;out["next_cursor"]=after;JsonArray events=out["events"].to<JsonArray>();
 if(includePersistent)readEventBacklog(out);else eventStorageStatus(out["event_storage"].to<JsonObject>());
 size_t persistentCount=out["persistent_events"].size();
 for(uint32_t seq=max(after+1,oldest);seq<=touchSeq&&events.size()+persistentCount<24;seq++){
  TouchRecord &r=touchQueue[(seq-1)%TOUCH_CAP];encodeTouchRecord(events.add<JsonObject>(),r,touchBoot);out["next_cursor"]=seq;
 }
}
