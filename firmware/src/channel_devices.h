#pragma once
#include <math.h>

// Logical IDs are independent of physical MUX ports. New drivers extend this registry.
static constexpr int MAX_CHANNELS=16;
enum class DeviceKind { PRESSURE, TEMPERATURE, VIBRATION };
enum class ChannelDriver { MUX_ADC, GPIO_ADC, SIMULATION, GPIO_PWM };
struct ChannelConfig {
 bool configured=false,enabled=true;
 String name;
 DeviceKind kind=DeviceKind::PRESSURE;
 ChannelDriver driver=ChannelDriver::MUX_ADC;
 int mux=-1,gpio=-1,on=1200,off=800;
 float r0=10000,beta=3950,pullDown=10000,series=4700,vcc=3300,offset=0;
 int sampleMs=1000,reportMs=30000;
};
struct ChannelReading {
 bool valid=false,sampled=false;
 float value=0;
 int raw=0,mv=-1;
 uint64_t at=0,lastSample=0,lastReport=0;
 float reported=0;
 String source="simulation",fault;
};
static ChannelConfig channels[MAX_CHANNELS];
static ChannelReading readings[MAX_CHANNELS];
static bool outputEnabled=false;
static int channelCount(){int n=0;for(auto &c:channels)if(c.configured)n++;return n;}
static const char* kindName(DeviceKind k){return k==DeviceKind::PRESSURE?"pressure":k==DeviceKind::TEMPERATURE?"temperature":"vibration";}
static const char* driverName(ChannelDriver d){switch(d){case ChannelDriver::MUX_ADC:return "mux_adc";case ChannelDriver::GPIO_ADC:return "gpio_adc";case ChannelDriver::GPIO_PWM:return "gpio_pwm";default:return "simulation";}}
static const char* unitName(DeviceKind k){return k==DeviceKind::PRESSURE?"adc_raw":k==DeviceKind::TEMPERATURE?"degC":"percent";}
static bool validChannel(int ch){return ch>=0&&ch<MAX_CHANNELS&&channels[ch].configured&&channels[ch].enabled;}
static void encodeChannels(JsonObject out,const ChannelConfig *list=channels){
 out["schema_version"]=1;out["max_channels"]=MAX_CHANNELS;
 JsonArray arr=out["channels"].to<JsonArray>();
 for(int i=0;i<MAX_CHANNELS;i++){
  const auto &c=list[i];if(!c.configured)continue;JsonObject p=arr.add<JsonObject>();
  p["channel"]=i;p["name"]=c.name;p["type"]=kindName(c.kind);p["enabled"]=c.enabled;
  p["direction"]=c.kind==DeviceKind::VIBRATION?"output":"input";p["driver"]=driverName(c.driver);
  if(c.driver==ChannelDriver::MUX_ADC)p["mux_port"]=c.mux;
  if(c.driver==ChannelDriver::GPIO_ADC||c.driver==ChannelDriver::GPIO_PWM)p["gpio"]=c.gpio;
  JsonObject a=p["options"].to<JsonObject>();
  if(c.kind==DeviceKind::PRESSURE){a["press_threshold"]=c.on;a["release_threshold"]=c.off;}
  if(c.kind==DeviceKind::TEMPERATURE){a["model"]="ntc_b3950";a["r0_ohm"]=c.r0;a["beta_kelvin"]=c.beta;a["pull_down_ohm"]=c.pullDown;a["series_ohm"]=c.series;a["supply_mv"]=c.vcc;a["offset_c"]=c.offset;a["sample_ms"]=c.sampleMs;a["report_ms"]=c.reportMs;}
 }
}
static bool numberOption(JsonObjectConst o,const char* key,float &dst,float lo,float hi,String &error){
 if(o[key].isNull())return true;
 if(!o[key].is<float>()){error=String(key)+" must be a finite number";return false;}
 float v=o[key].as<float>();if(!isfinite(v)||v<lo||v>hi){error=String(key)+" is outside supported range";return false;}dst=v;return true;
}
static bool intOption(JsonObjectConst o,const char* key,int &dst,int lo,int hi,String &error){
 if(o[key].isNull())return true;
 if(!o[key].is<int>()){error=String(key)+" must be integer";return false;}
 int v=o[key];if(v<lo||v>hi){error=String(key)+" is outside supported range";return false;}dst=v;return true;
}
static bool parseChannels(JsonVariantConst a,ChannelConfig *next,String &error){
 if(!a["channels"].is<JsonArrayConst>()||a["channels"].size()<1||a["channels"].size()>MAX_CHANNELS){error="Provide 1..16 channel configurations";return false;}
 if(!a["schema_version"].isNull()&&(!a["schema_version"].is<int>()||a["schema_version"].as<int>()!=1)){error="Unsupported schema_version";return false;}
 bool muxUsed[8]={},gpioUsed[22]={};
 for(JsonVariantConst entry:a["channels"].as<JsonArrayConst>()){
  if(!entry.is<JsonObjectConst>()){error="Each channel must be an object";return false;}
  JsonObjectConst p=entry.as<JsonObjectConst>();
  if(!p["channel"].is<int>()||!p["name"].is<String>()||!p["type"].is<String>()||!p["driver"].is<String>()){error="channel/name/type/driver required";return false;}
  int id=p["channel"];String name=p["name"].as<String>(),type=p["type"].as<String>(),driver=p["driver"].as<String>();
  if(id<0||id>=MAX_CHANNELS||next[id].configured||name.isEmpty()||name.length()>96){error="Unique IDs 0..15 and names 1..96 UTF-8 bytes required";return false;}
  ChannelConfig c;c.configured=true;c.name=name;
  if(!p["enabled"].isNull()&&!p["enabled"].is<bool>()){error="enabled must be boolean";return false;}c.enabled=p["enabled"]|true;
  if(type=="pressure")c.kind=DeviceKind::PRESSURE;
  else if(type=="temperature")c.kind=DeviceKind::TEMPERATURE;
  else if(type=="vibration")c.kind=DeviceKind::VIBRATION;
  else{error="Unknown type; use pressure, temperature or vibration";return false;}
  if(driver=="simulation")c.driver=ChannelDriver::SIMULATION;
  else if(driver=="mux_adc"&&c.kind!=DeviceKind::VIBRATION)c.driver=ChannelDriver::MUX_ADC;
  else if(driver=="gpio_adc"&&c.kind!=DeviceKind::VIBRATION)c.driver=ChannelDriver::GPIO_ADC;
  else if(driver=="gpio_pwm"&&c.kind==DeviceKind::VIBRATION)c.driver=ChannelDriver::GPIO_PWM;
  else{error="Driver is unsupported or incompatible with direction/type";return false;}
  if(!p["direction"].isNull()&&p["direction"].as<String>()!=(c.kind==DeviceKind::VIBRATION?"output":"input")){error="direction conflicts with type";return false;}
  if(c.driver==ChannelDriver::MUX_ADC){
   if(!p["mux_port"].is<int>()){error="mux_port 0..7 required";return false;}c.mux=p["mux_port"];
   if(c.mux<0||c.mux>7||muxUsed[c.mux]){error="4051 ports must be unique, 0..7";return false;}muxUsed[c.mux]=true;
  }
  if(c.driver==ChannelDriver::GPIO_ADC||c.driver==ChannelDriver::GPIO_PWM){
   if(!p["gpio"].is<int>()){error="gpio required";return false;}c.gpio=p["gpio"];
   bool allowed=c.driver==ChannelDriver::GPIO_ADC?c.gpio==1:(c.gpio==6||c.gpio==7||c.gpio==10);
   if(!allowed||gpioUsed[c.gpio]){error="GPIO ADC:1; PWM:6/7/10, unique. Reserved pins forbidden";return false;}gpioUsed[c.gpio]=true;
  }
  if(!p["options"].isNull()&&!p["options"].is<JsonObjectConst>()){error="options must be object";return false;}
  JsonObjectConst o=p["options"].as<JsonObjectConst>();
  for(JsonPairConst option:o){
   String key=option.key().c_str();
   bool known=c.kind==DeviceKind::PRESSURE?(key=="press_threshold"||key=="release_threshold"):
    c.kind==DeviceKind::TEMPERATURE?(key=="model"||key=="r0_ohm"||key=="beta_kelvin"||key=="pull_down_ohm"||key=="series_ohm"||key=="supply_mv"||key=="offset_c"||key=="sample_ms"||key=="report_ms"):false;
   if(!known){error="Unknown option for selected type: "+key;return false;}
  }
  if(c.kind==DeviceKind::PRESSURE){
   if(!intOption(o,"press_threshold",c.on,1,4095,error)||!intOption(o,"release_threshold",c.off,0,4094,error))return false;
   if(c.off>=c.on){error="release_threshold must be below press_threshold";return false;}
  }
  if(c.kind==DeviceKind::TEMPERATURE){
   if(!o["model"].isNull()&&o["model"]!="ntc_b3950"){error="Only ntc_b3950 temperature model is installed";return false;}
   if(c.driver==ChannelDriver::GPIO_ADC)c.series=0;
   if(!numberOption(o,"r0_ohm",c.r0,100,1000000,error)||!numberOption(o,"beta_kelvin",c.beta,1000,6000,error)||!numberOption(o,"pull_down_ohm",c.pullDown,100,1000000,error)||!numberOption(o,"series_ohm",c.series,0,100000,error)||!numberOption(o,"supply_mv",c.vcc,1000,3600,error)||!numberOption(o,"offset_c",c.offset,-30,30,error)||!intOption(o,"sample_ms",c.sampleMs,500,60000,error)||!intOption(o,"report_ms",c.reportMs,1000,60000,error))return false;
   if(c.reportMs<c.sampleMs){error="report_ms must be >= sample_ms";return false;}
  }
  // Reject silently misspelled fields rather than saving an ineffective binding.
  for(JsonPairConst prop:p){String key=prop.key().c_str();if(key!="channel"&&key!="name"&&key!="type"&&key!="driver"&&key!="direction"&&key!="enabled"&&key!="mux_port"&&key!="gpio"&&key!="options"){error="Unknown channel field: "+key;return false;}}
  if((!p["gpio"].isNull()&&c.driver!=ChannelDriver::GPIO_ADC&&c.driver!=ChannelDriver::GPIO_PWM)||(!p["mux_port"].isNull()&&c.driver!=ChannelDriver::MUX_ADC)){error="Remove binding fields unused by the selected driver";return false;}
  next[id]=c;
 }
 return true;
}
static void channelCapabilities(JsonObject out){
 out["schema_version"]=1;out["max_channels"]=MAX_CHANNELS;out["mux_ports"]=8;out["adc_gpio"]=0;
 out["physical_inputs_enabled"]=sensorEnabled; // defined by touch_events before this function is included
 out["physical_outputs_enabled"]=outputEnabled;
 JsonArray types=out["types"].to<JsonArray>();
 for(auto kind:{DeviceKind::PRESSURE,DeviceKind::TEMPERATURE,DeviceKind::VIBRATION}){
  JsonObject t=types.add<JsonObject>();t["type"]=kindName(kind);t["direction"]=kind==DeviceKind::VIBRATION?"output":"input";t["unit"]=unitName(kind);
  t["model"]=kind==DeviceKind::PRESSURE?"fsr_adc":kind==DeviceKind::TEMPERATURE?"ntc_b3950":"erm_pwm";
  JsonArray d=t["drivers"].to<JsonArray>();d.add("simulation");if(kind==DeviceKind::VIBRATION)d.add("gpio_pwm");else{d.add("mux_adc");d.add("gpio_adc");}
 }
 JsonArray gpio=out["pwm_gpio"].to<JsonArray>();gpio.add(6);gpio.add(7);gpio.add(10);
 out["direct_adc_gpio"]=1;out["max_vibration_ms"]=5000;
 out["temperature_wiring"]="3V3 -> series resistor -> NTC -> ADC node -> pull-down -> GND; configurable resistor values";
 out["expansion"]="16 logical slots; 8 unique physical 4051 inputs. Additional protocols require a new driver/hardware, not renaming a type.";
 out["vibration_wiring"]="Independent GPIO and external transistor/MOSFET motor driver; never motor direct to MCU or 4051.";
}
