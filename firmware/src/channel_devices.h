#pragma once
#include <math.h>
#include "expansion_inputs.h"
static constexpr int MAX_CHANNELS=16;
enum class DeviceKind { PRESSURE, TEMPERATURE, VIBRATION, MOTION, LIGHT, SWITCH };
enum class ChannelDriver { MUX_ADC, GPIO_ADC, SIMULATION, GPIO_PWM, DS18B20, LIS3DH, GPIO_SWITCH };
struct ChannelConfig {
 bool configured=false,enabled=true,simulate=false;
 String name;DeviceKind kind=DeviceKind::PRESSURE;ChannelDriver driver=ChannelDriver::MUX_ADC;
 int mux=-1,gpio=-1,on=1200,off=800,sampleMs=1000,debounceMs=40;bool activeLow=true;
};
struct ChannelReading {bool valid=false,sampled=false;float value=0;int raw=0,mv=-1;uint64_t at=0;String source="simulation",fault;};
static ChannelConfig channels[MAX_CHANNELS];static ChannelReading readings[MAX_CHANNELS];
static constexpr bool outputEnabled=false;
// Removed rows are preserved as opaque configuration data, never executed.
static String retiredChannels="[]";
static int retiredChannelCount=0;
static int channelCount(){int n=0;for(auto &c:channels)if(c.configured)n++;return n;}
static bool outputKind(DeviceKind k){return k==DeviceKind::VIBRATION||k==DeviceKind::LIGHT;}
static const char* kindName(DeviceKind k){switch(k){case DeviceKind::PRESSURE:return "pressure";case DeviceKind::TEMPERATURE:return "temperature";case DeviceKind::VIBRATION:return "vibration";case DeviceKind::MOTION:return "motion";case DeviceKind::LIGHT:return "light";default:return "switch";}}
static const char* driverName(ChannelDriver d){return d==ChannelDriver::MUX_ADC?"mux_adc":d==ChannelDriver::GPIO_ADC?"gpio_adc":d==ChannelDriver::GPIO_SWITCH?"gpio_switch":"simulation";}
static const char* unitName(DeviceKind k){return k==DeviceKind::PRESSURE?"adc_raw":"boolean";}
static bool validChannel(int ch){return ch>=0&&ch<MAX_CHANNELS&&channels[ch].configured&&channels[ch].enabled;}
static const char* channelMode(const ChannelConfig &c){return !c.enabled?"off":(c.simulate||c.driver==ChannelDriver::SIMULATION)?"simulation":"connected";}
static bool physicalChannel(const ChannelConfig &c){return c.configured&&c.enabled&&!c.simulate&&c.driver!=ChannelDriver::SIMULATION;}
static const char* inputModeSummary(){bool physical=false,simulation=false;for(const auto &c:channels)if(c.configured&&c.enabled){if(physicalChannel(c))physical=true;else simulation=true;}return physical?(sensorEnabled?(simulation?"mixed":"sensor"):"paused"):(simulation?"simulation":"off");}
static void encodeChannels(JsonObject out,const ChannelConfig *list=channels){
 out["schema_version"]=1;out["max_channels"]=MAX_CHANNELS;out["port_state_model"]="per_port_v1";out["retired_channel_count"]=retiredChannelCount;
 JsonArray arr=out["channels"].to<JsonArray>();
 for(int i=0;i<MAX_CHANNELS;i++){const auto &c=list[i];if(!c.configured)continue;JsonObject p=arr.add<JsonObject>();p["channel"]=i;p["name"]=c.name;p["type"]=kindName(c.kind);p["enabled"]=c.enabled;p["mode"]=channelMode(c);p["direction"]="input";p["driver"]=driverName(c.driver);
 if(c.driver==ChannelDriver::MUX_ADC)p["mux_port"]=c.mux;
 if(c.driver==ChannelDriver::GPIO_ADC||c.driver==ChannelDriver::GPIO_SWITCH)p["gpio"]=c.gpio;
 JsonObject o=p["options"].to<JsonObject>();if(c.kind==DeviceKind::PRESSURE){o["press_threshold"]=c.on;o["release_threshold"]=c.off;}else{o["active_low"]=c.activeLow;o["debounce_ms"]=c.debounceMs;}}
}
static bool intOption(JsonObjectConst o,const char* key,int &dst,int lo,int hi,String &error){if(o[key].isNull())return true;if(!o[key].is<int>()){error=String(key)+" must be integer";return false;}int v=o[key];if(v<lo||v>hi){error=String(key)+" is outside supported range";return false;}dst=v;return true;}
static bool parseChannels(JsonVariantConst a,ChannelConfig *next,String &error){
 if(!a["channels"].is<JsonArrayConst>()||a["channels"].size()<1||a["channels"].size()>MAX_CHANNELS){error="Provide 1..16 channel configurations";return false;}
 if(!a["schema_version"].isNull()&&(!a["schema_version"].is<int>()||a["schema_version"].as<int>()!=1)){error="Unsupported schema_version";return false;}
 bool muxUsed[8]={},gpioUsed[22]={};
 for(JsonVariantConst entry:a["channels"].as<JsonArrayConst>()){
 if(!entry.is<JsonObjectConst>()){error="Each channel must be an object";return false;}JsonObjectConst p=entry.as<JsonObjectConst>();
 if(!p["channel"].is<int>()||!p["name"].is<String>()||!p["type"].is<String>()||!p["driver"].is<String>()){error="channel/name/type/driver required";return false;}
 int id=p["channel"];String name=p["name"].as<String>(),type=p["type"].as<String>(),driver=p["driver"].as<String>();
 if(id<0||id>=MAX_CHANNELS||next[id].configured||name.isEmpty()||name.length()>96){error="Unique IDs 0..15 and names 1..96 UTF-8 bytes required";return false;}
 ChannelConfig c;c.configured=true;c.name=name;
 if(!p["enabled"].isNull()&&!p["enabled"].is<bool>()){error="enabled must be boolean";return false;}c.enabled=p["enabled"]|true;
 if(type=="pressure")c.kind=DeviceKind::PRESSURE;else if(type=="switch")c.kind=DeviceKind::SWITCH;else{error="This firmware supports pressure and switch inputs only";return false;}
 if(driver=="simulation")c.driver=ChannelDriver::SIMULATION;else if(type=="pressure"&&driver=="mux_adc")c.driver=ChannelDriver::MUX_ADC;else if(type=="pressure"&&driver=="gpio_adc")c.driver=ChannelDriver::GPIO_ADC;else if(type=="switch"&&driver=="gpio_switch")c.driver=ChannelDriver::GPIO_SWITCH;else{error="Unsupported input driver";return false;}
 if(!p["mode"].isNull()){if(!p["mode"].is<String>()){error="mode must be a string";return false;}String mode=p["mode"].as<String>();if(mode!="off"&&mode!="simulation"&&mode!="connected"){error="mode must be off, simulation or connected";return false;}if(!p["enabled"].isNull()&&p["enabled"].as<bool>()!=(mode!="off")){error="enabled conflicts with mode";return false;}if(mode=="connected"&&c.driver==ChannelDriver::SIMULATION){error="Physical binding required";return false;}c.enabled=mode!="off";c.simulate=mode=="simulation";}
 if(!p["direction"].isNull()&&p["direction"]!="input"){error="Only input channels are supported";return false;}
 if(c.driver==ChannelDriver::MUX_ADC){if(!p["mux_port"].is<int>()){error="mux_port 0..7 required";return false;}c.mux=p["mux_port"];if(c.mux<0||c.mux>7||muxUsed[c.mux]){error="4051 ports must be unique, 0..7";return false;}muxUsed[c.mux]=true;}
 if(c.driver==ChannelDriver::GPIO_ADC||c.driver==ChannelDriver::GPIO_SWITCH){if(!p["gpio"].is<int>()){error="gpio required";return false;}c.gpio=p["gpio"];if(c.gpio!=(c.driver==ChannelDriver::GPIO_ADC?1:21)||gpioUsed[c.gpio]){error="GPIO resource conflict; ADC=1, switch=21";return false;}gpioUsed[c.gpio]=true;}
 if(!p["options"].isNull()&&!p["options"].is<JsonObjectConst>()){error="options must be object";return false;}JsonObjectConst o=p["options"].as<JsonObjectConst>();
 for(JsonPairConst option:o){String key=option.key().c_str();if(c.kind==DeviceKind::PRESSURE?key!="press_threshold"&&key!="release_threshold":key!="active_low"&&key!="debounce_ms"){error="Unknown option for selected type: "+key;return false;}}
 if(c.kind==DeviceKind::PRESSURE){if(!intOption(o,"press_threshold",c.on,1,4095,error)||!intOption(o,"release_threshold",c.off,0,4094,error))return false;if(c.off>=c.on){error="release_threshold must be below press_threshold";return false;}}
 else{if(!o["active_low"].isNull()&&!o["active_low"].is<bool>()){error="active_low boolean required";return false;}c.activeLow=o["active_low"]|true;if(!intOption(o,"debounce_ms",c.debounceMs,20,500,error))return false;}
 for(JsonPairConst prop:p){String key=prop.key().c_str();if(key!="channel"&&key!="name"&&key!="type"&&key!="driver"&&key!="direction"&&key!="enabled"&&key!="mode"&&key!="mux_port"&&key!="gpio"&&key!="options"){error="Unknown channel field: "+key;return false;}}
 if((!p["gpio"].isNull()&&c.driver!=ChannelDriver::GPIO_ADC&&c.driver!=ChannelDriver::GPIO_SWITCH)||(!p["mux_port"].isNull()&&c.driver!=ChannelDriver::MUX_ADC)){error="Remove unused binding fields";return false;}next[id]=c;
 }return true;
}
// Split only explicitly retired types. Unknown or corrupt input rows still fail validation.
static void retireUnsupportedChannels(JsonDocument &stored){
 JsonDocument retired;if(deserializeJson(retired,retiredChannels))retired.to<JsonArray>();
 if(stored["retired_channels"].is<JsonArray>())for(JsonVariantConst row:stored["retired_channels"].as<JsonArrayConst>())retired.as<JsonArray>().add(row);
 JsonArray rows=stored["channels"].as<JsonArray>();
 for(size_t i=0;i<rows.size();){String type=rows[i]["type"]|"";
 if(type=="temperature"||type=="motion"||type=="vibration"||type=="light"){retired.as<JsonArray>().add(rows[i]);rows.remove(i);}else i++;}
 retiredChannels="";serializeJson(retired,retiredChannels);retiredChannelCount=retired.size();
}
static void channelCapabilities(JsonObject out){
 out["schema_version"]=1;out["max_channels"]=MAX_CHANNELS;out["mux_ports"]=8;out["adc_gpio"]=0;out["port_state_model"]="per_port_v1";out["presence_source"]="saved_installation_config";out["electrical_presence_detection"]=false;
 out["physical_inputs_enabled"]=sensorEnabled;out["physical_outputs_enabled"]=false;out["physical_outputs_supported"]=false;out["retired_channel_count"]=retiredChannelCount;
 JsonArray types=out["types"].to<JsonArray>();for(auto k:{DeviceKind::PRESSURE,DeviceKind::SWITCH}){JsonObject t=types.add<JsonObject>();t["type"]=kindName(k);t["direction"]="input";t["unit"]=unitName(k);t["model"]=k==DeviceKind::PRESSURE?"fsr_adc":"dry_contact";JsonArray d=t["drivers"].to<JsonArray>();d.add("simulation");if(k==DeviceKind::PRESSURE){d.add("mux_adc");d.add("gpio_adc");}else d.add("gpio_switch");}
 out["direct_adc_gpio"]=1;out["switch_gpio"]=21;out["expansion"]="Pressure ADC and dry-contact switch only; temperature, motion and actuator drivers removed.";
}
