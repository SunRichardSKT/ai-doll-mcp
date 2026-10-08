#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <esp_system.h>

// SuperMini firmware: simulation by default; physical 74HC4051 sampling is opt-in.
static WebServer web(80);
static DNSServer dns;
static Preferences prefs;
static String apName, apPass, token, ssid, password, serialLine;
static bool mcpEnabled=true, led=false, connectPending=false;
static uint32_t connectAt=0, lastAttempt=0, pressUntil=0;
static int pressChannel=-1, pressValue=0, lastWifi=-1;
static constexpr int LED_PIN=8; // Common SuperMini blue LED, active low.
static bool scanBusy=false;
static uint32_t scanStartedAt=0;
static const char* VERSION="doll-lab-2.4.0";
static const char* PROTOCOL="2025-11-25";

static String encode(const JsonDocument &d){String s;serializeJson(d,s);return s;}
// Avoid a full final 64-byte USB packet: some CDC hosts wait for a short packet/ZLP.
static void serialJson(const JsonDocument &d){String line=encode(d);if((line.length()+1)%64==0)line+=' ';line+='\n';Serial.print(line);Serial.flush();}
static String randomHex(){char b[33];snprintf(b,sizeof(b),"%08lx%08lx%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random());return String(b);}
#include "touch_events.h"
#include "channel_rpc.h"
static void setLed(bool on){led=on;digitalWrite(LED_PIN,on?LOW:HIGH);}
#include "network_state.h"
#include "device_discovery.h"
static void status(JsonObject o){
 o["network_mode"]=networkModeName();o["config_ap_open"]=configAP;o["setup_button_gpio"]=SETUP_BUTTON_PIN;
 o["boot_id"]=touchBoot;o["event_cursor"]=touchSeq;
 o["firmware"]=VERSION;o["device_id"]=apName;o["uptime_ms"]=millis();o["free_heap"]=ESP.getFreeHeap();
 o["wifi_connected"]=WiFi.status()==WL_CONNECTED;o["wifi_status"]=(int)WiFi.status();o["ssid"]=ssid;
 o["ip"]=WiFi.localIP().toString();o["ap_ip"]=WiFi.softAPIP().toString();o["ap_ssid"]=apName;
 o["mcp_enabled"]=mcpEnabled;o["mcp_path"]="/mcp";o["protocol_version"]=PROTOCOL;
 o["discovery_protocol"]=DISCOVERY_PROTOCOL;o["discovery_port"]=DISCOVERY_PORT;o["discovery_active"]=discoveryActive;
 o["led_on"]=led;o["led_gpio_level"]=digitalRead(LED_PIN);o["sensor_mode"]=sensorEnabled?"sensor":"simulation";o["sensor_count"]=channelCount();o["max_channels"]=MAX_CHANNELS;o["physical_outputs_enabled"]=outputEnabled;
 o["pressed_channel"]=pressChannel;o["pressure"]=pressValue;
 o["reaction"]=pressValue>=2500?"抱抱收到啦！":pressValue>=700?"我感受到你的轻轻按压了。":"安静等待触摸";
}
static void scanWifi(JsonObject out,bool start){
 int n=WiFi.scanComplete();
 if(scanBusy && (n>=0 || millis()-scanStartedAt>25000))scanBusy=false;
 if(start && !scanBusy){
  if(connectPending){out["error"]="正在连接网络，请稍后重试";return;}
  WiFi.scanDelete();n=WiFi.scanNetworks(true,false,false,600);
  scanBusy=n==WIFI_SCAN_RUNNING;scanStartedAt=millis();
 }
 out["scanning"]=scanBusy;
 JsonArray networks=out["networks"].to<JsonArray>();
 if(scanBusy)return;
 if(n<0){out["error"]="扫描失败，请稍后重新扫描";return;}
 // Return the strongest visible SSIDs, without duplicate access points.
 int lastRssi=1,lastIndex=-1;
 for(int count=0;count<n && networks.size()<30;count++){
  int best=-1,bestRssi=-1000;
  for(int i=0;i<n && i<256;i++){
   int r=WiFi.RSSI(i);
   if((r<lastRssi || (r==lastRssi && i>lastIndex)) && r>bestRssi){best=i;bestRssi=r;}
  }
  if(best<0)break;
  lastRssi=bestRssi;lastIndex=best;
  String name=WiFi.SSID(best);if(name.isEmpty())continue;
  bool duplicate=false;for(JsonObject item:networks)if(item["ssid"].as<String>()==name){duplicate=true;break;}
  if(duplicate)continue;
  JsonObject item=networks.add<JsonObject>();item["ssid"]=name;item["rssi"]=bestRssi;
  item["secure"]=WiFi.encryptionType(best)!=WIFI_AUTH_OPEN;
 }
}
static bool provision(JsonVariantConst p,String &error){
 if(scanBusy){error="扫描进行中，请稍后连接";return false;}
 if(!p["ssid"].is<String>() || !p["password"].is<String>()){error="ssid/password must be strings";return false;}
 String s=p["ssid"].as<String>(),w=p["password"].as<String>();
 if(s.length()<1||s.length()>32||w.length()>63||(w.length()>0&&w.length()<8)){error="SSID 1..32 bytes; password empty or 8..63 bytes";return false;}
 ssid=s;password=w;prefs.putString("ssid",ssid);prefs.putString("pass",password);
 connectPending=true;connectAt=millis()+500;return true;
}
static void rpcError(JsonDocument &out,int code,const char* msg){out.remove("result");out["error"]["code"]=code;out["error"]["message"]=msg;}
static void resultText(JsonDocument &out,const JsonDocument &data,bool error=false){
 JsonObject r=out["result"].to<JsonObject>();r["isError"]=error;
 JsonObject c=r["content"].to<JsonArray>().add<JsonObject>();c["type"]="text";c["text"]=encode(data);
}
static JsonDocument rpc(const JsonDocument &in){
 JsonDocument out;out["jsonrpc"]="2.0";out["id"]=in["id"];
 if(in["jsonrpc"]!="2.0"||!in["method"].is<String>()){rpcError(out,-32600,"Invalid Request");return out;}
 String method=in["method"].as<String>();
 if(method=="initialize"){
  out["result"]["protocolVersion"]=PROTOCOL;out["result"]["capabilities"]["tools"]["listChanged"]=false;
  out["result"]["serverInfo"]["name"]="ai-doll-esp32c3";out["result"]["serverInfo"]["version"]=VERSION;
 }else if(method=="ping"){out["result"].to<JsonObject>();}
 else if(method=="tools/list"){
  JsonArray tools=out["result"]["tools"].to<JsonArray>();
  auto add=[&](const char* name,const char* desc){JsonObject t=tools.add<JsonObject>();t["name"]=name;t["description"]=desc;t["inputSchema"]["type"]="object";t["inputSchema"]["properties"].to<JsonObject>();t["inputSchema"]["additionalProperties"]=false;return t;};
  add("get_sensor_config","Read physical 74HC4051 acquisition mode, raw readings and thresholds.");
  JsonObject st=add("set_sensor_config","Explicitly enable physical 4051 sampling only with assembled hardware. Reboot returns to simulation. GPIO ADC=0, S0/S1/S2=3/4/5.");
  st["inputSchema"]["properties"]["enabled"]["type"]="boolean";
  st["inputSchema"]["properties"]["press_threshold"]["type"]="integer";
  st["inputSchema"]["properties"]["release_threshold"]["type"]="integer";
  JsonArray sr=st["inputSchema"]["required"].to<JsonArray>();sr.add("enabled");sr.add("press_threshold");sr.add("release_threshold");
  add("get_body_map","Read user-defined sensor body names from device.");
  JsonObject mapTool=add("set_body_map","Save names for all configured channels on device; historical events keep original names.");
  mapTool["inputSchema"]["properties"]["parts"]["type"]="array";
  mapTool["inputSchema"]["properties"]["parts"]["minItems"]=1;
  mapTool["inputSchema"]["properties"]["parts"]["maxItems"]=MAX_CHANNELS;
  JsonObject item=mapTool["inputSchema"]["properties"]["parts"]["items"].to<JsonObject>();
  item["type"]="object";item["properties"]["channel"]["type"]="integer";item["properties"]["channel"]["minimum"]=0;item["properties"]["channel"]["maximum"]=MAX_CHANNELS-1;
  item["properties"]["name"]["type"]="string";item["required"].to<JsonArray>().add("channel");item["required"].as<JsonArray>().add("name");
  mapTool["inputSchema"]["required"].to<JsonArray>().add("parts");
  JsonObject et=add("get_touch_events","Read bounded device RAM queue. Use companion MCP for persistent history and interaction sessions.");
  et["inputSchema"]["properties"]["after"]["type"]="integer";et["inputSchema"]["properties"]["after"]["minimum"]=0;
  et["inputSchema"]["properties"]["boot_id"]["type"]="string";
  add("doll_get_status","Read device Wi-Fi, uptime, LED and simulated pressure state.");
  JsonObject t=add("doll_simulate_press","Inject a simulated FSR press; does not read a physical sensor. Auto releases after five seconds.");
  t["inputSchema"]["properties"]["channel"]["type"]="integer";t["inputSchema"]["properties"]["channel"]["minimum"]=0;t["inputSchema"]["properties"]["channel"]["maximum"]=MAX_CHANNELS-1;
  t["inputSchema"]["properties"]["value"]["type"]="integer";t["inputSchema"]["properties"]["value"]["minimum"]=0;t["inputSchema"]["properties"]["value"]["maximum"]=4095;
  t["inputSchema"]["required"].to<JsonArray>().add("channel");t["inputSchema"]["required"].as<JsonArray>().add("value");
  t=add("doll_set_led","Set the SuperMini active-low GPIO8 LED for a visible hardware test.");t["inputSchema"]["properties"]["on"]["type"]="boolean";t["inputSchema"]["required"].to<JsonArray>().add("on");
  addChannelTools(tools);
 }else if(method=="tools/call"){
  String name=in["params"]["name"]|"";JsonVariantConst a=in["params"]["arguments"];JsonDocument data;
  if(name=="get_channel_capabilities"){channelCapabilities(data.to<JsonObject>());}
  else if(name=="get_channel_config"){encodeChannels(data.to<JsonObject>());}
  else if(name=="set_channel_config"){String error;if(!saveChannels(a,error)){rpcError(out,-32602,error.c_str());return out;}encodeChannels(data.to<JsonObject>());}
  else if(name=="read_channel_values"){readChannels(data.to<JsonObject>());}
  else if(name=="set_input_enabled"){String error;if(!setInputEnabled(a,error)){rpcError(out,-32602,error.c_str());return out;}readChannels(data.to<JsonObject>());}
  else if(name=="get_operating_mode"){operatingMode(data.to<JsonObject>());}
  else if(name=="set_operating_mode"){String error;if(!setOperatingMode(a,error)){rpcError(out,-32602,error.c_str());return out;}operatingMode(data.to<JsonObject>());}
  else if(name=="capture_pressure_calibration"){String error;if(!captureCalibration(a,error)){rpcError(out,-32602,error.c_str());return out;}calibrationStatus(data.to<JsonObject>());}
  else if(name=="get_pressure_calibration"){calibrationStatus(data.to<JsonObject>());}
  else if(name=="apply_pressure_calibration"){String error;if(!applyCalibration(error)){rpcError(out,-32602,error.c_str());return out;}calibrationStatus(data.to<JsonObject>());}
  else if(name=="cancel_pressure_calibration"){calibration.engaged=false;calibration.capturing=false;calibrationStatus(data.to<JsonObject>());}
  else if(name=="simulate_channel_input"){String error;if(!simulateInput(a,error)){rpcError(out,-32602,error.c_str());return out;}readChannels(data.to<JsonObject>());}
  else if(name=="set_output_enabled"){String error;if(!armOutputs(a,error)){rpcError(out,-32602,error.c_str());return out;}readChannels(data.to<JsonObject>());}
  else if(name=="set_vibration"){String error;if(!vibrate(a,error)){rpcError(out,-32602,error.c_str());return out;}readChannels(data.to<JsonObject>());}
  else if(name=="get_sensor_config"){sensorConfig(data.to<JsonObject>());}
  else if(name=="set_sensor_config"){String error;if(!setSensors(a,error)){rpcError(out,-32602,error.c_str());return out;}sensorConfig(data.to<JsonObject>());}
  else if(name=="get_body_map"){bodyMap(data.to<JsonObject>());}
  else if(name=="set_body_map"){String error;if(!saveBodyMap(a,error)){rpcError(out,-32602,error.c_str());return out;}bodyMap(data.to<JsonObject>());}
  else if(name=="get_touch_events"){if(!a["after"].isNull()&&!a["after"].is<uint32_t>()){rpcError(out,-32602,"after must be nonnegative integer");return out;}touchRead(data.to<JsonObject>(),a["after"]|0U,a["boot_id"]|"");}
  else if(name=="doll_get_status"){status(data.to<JsonObject>());}
  else if(name=="doll_set_led"){
   if(!a["on"].is<bool>()){rpcError(out,-32602,"on must be boolean");return out;}setLed(a["on"].as<bool>());ledOverrideUntil=millis()+3000;status(data.to<JsonObject>());
  }else if(name=="doll_simulate_press"){
   int ch=a["channel"]|-1;
   if(!a["channel"].is<int>()||!a["value"].is<int>()||!validChannel(ch)||channels[ch].kind!=DeviceKind::PRESSURE){rpcError(out,-32602,"Choose an enabled pressure channel; value integer 0..4095");return out;}
   String error;if(!simulateInput(a,error)){rpcError(out,-32602,error.c_str());return out;}
   status(data.to<JsonObject>());JsonDocument event;event["event"]="simulated_press";event["channel"]=pressChannel;event["value"]=pressValue;event["reaction"]=data["reaction"];serialJson(event);
  }else{rpcError(out,-32602,"Unknown tool");return out;}
  resultText(out,data);
 }else{rpcError(out,-32601,"Method not found");}
 return out;
}
static bool admin(){if(configAP)return true;if(web.authenticate("admin",apPass.c_str()))return true;web.requestAuthentication();return false;}
static bool originOK(){String o=web.header("Origin");return o.isEmpty()||o=="http://"+WiFi.softAPIP().toString()||(WiFi.status()==WL_CONNECTED&&o=="http://"+WiFi.localIP().toString());}
static void sendJson(int code,const JsonDocument &d){web.sendHeader("Cache-Control","no-store");web.send(code,"application/json; charset=utf-8",encode(d));}
#include "device_page.h"
#include "channel_editor_asset.h"

static void serialCommand(const String &line){
 JsonDocument in,out;if(deserializeJson(in,line)){out["error"]="invalid JSON";serialJson(out);return;}
 String cmd=in["cmd"]|"";
 if(cmd=="status")status(out.to<JsonObject>());
 else if(cmd=="events")touchRead(out.to<JsonObject>(),in["after"]|0U,in["boot_id"]|"");
 else if(cmd=="setup_mode"){openConfigAP(NetworkMode::SETUP);out["ok"]=true;}
 else if(cmd=="scan")scanWifi(out.to<JsonObject>(),in["start"]|false);
 else if(cmd=="setup"){out["ap_ssid"]=apName;out["ap_password"]=apPass;out["admin_user"]="admin";out["mcp_token"]=token;}
 else if(cmd=="wifi"){String error;out["ok"]=provision(in.as<JsonVariantConst>(),error);if(error.length())out["error"]=error;}
 else if(cmd=="mcp"){if(!in["enabled"].is<bool>()){out["error"]="enabled must be boolean";}else{mcpEnabled=in["enabled"];prefs.putBool("mcp",mcpEnabled);out["ok"]=true;}}
 else if(cmd=="rpc"){if(!mcpEnabled){out["error"]="MCP disabled";}else{JsonDocument req;req.set(in["request"]);out=rpc(req);}}
 else if(cmd=="reboot"){Serial.println("{\"ok\":true,\"reboot\":true}");Serial.flush();delay(100);ESP.restart();}
 else out["error"]="unknown command";
 serialJson(out);
}

void setup(){
 pinMode(LED_PIN,OUTPUT);setLed(false);Serial.setRxBufferSize(16384);Serial.setTxBufferSize(32768);Serial.setTxTimeoutMs(500);Serial.begin(115200);prefs.begin("doll-lab",false);touchInit();
 uint64_t mac=ESP.getEfuseMac();char suffix[7];snprintf(suffix,sizeof(suffix),"%06lx",(unsigned long)(mac&0xffffff));apName="AI-Doll-"+String(suffix);
 apPass=prefs.getString("apkey","");if(apPass.isEmpty()){apPass="Doll-"+randomHex().substring(0,10);prefs.putString("apkey",apPass);}
 token=prefs.getString("token","");if(token.isEmpty()){token=randomHex();prefs.putString("token",token);}
 ssid=prefs.getString("ssid","");password=prefs.getString("pass","");mcpEnabled=prefs.getBool("mcp",true);
 networkInit();
 const char* headers[]={"Authorization","Origin","X-Setup-Token","MCP-Protocol-Version"};web.collectHeaders(headers,4);
 web.on("/",HTTP_GET,[]{if(admin())web.send_P(200,"text/html; charset=utf-8",PAGE);});
 web.on("/channel-editor.js",HTTP_GET,[]{if(admin())web.send_P(200,"application/javascript; charset=utf-8",CHANNEL_EDITOR_JS);});
 web.on("/api/setup",HTTP_GET,[]{if(!admin())return;JsonDocument d;d["token"]=token;d["enabled"]=mcpEnabled;d["admin_password"]=apPass;d["network_mode"]=networkModeName();sendJson(200,d);});
 web.on("/api/tool",HTTP_POST,[]{if(!admin())return;if(!originOK()||web.header("X-Setup-Token")!=token){web.send(403,"text/plain","Forbidden");return;}JsonDocument in;if(web.arg("plain").length()>16384||deserializeJson(in,web.arg("plain"))){web.send(400,"text/plain","Invalid JSON");return;}sendJson(200,rpc(in));});
 web.on("/api/status",HTTP_GET,[]{if(!admin())return;JsonDocument d;status(d.to<JsonObject>());sendJson(200,d);});
 web.on("/api/scan",HTTP_POST,[]{if(!admin())return;if(!originOK()||web.header("X-Setup-Token")!=token){web.send(403,"text/plain","Forbidden");return;}JsonDocument in,out;if(web.arg("plain").length()>128||deserializeJson(in,web.arg("plain"))){web.send(400,"text/plain","Invalid JSON");return;}scanWifi(out.to<JsonObject>(),in["start"]|false);sendJson(200,out);});
 auto config=[](){if(!admin())return;if(!originOK()||web.header("X-Setup-Token")!=token){web.send(403,"text/plain","Forbidden");return;}JsonDocument in,out;if(web.arg("plain").length()>1024||deserializeJson(in,web.arg("plain"))){web.send(400,"text/plain","Invalid JSON");return;}
  if(web.uri()=="/api/wifi"){String error;bool ok=provision(in.as<JsonVariantConst>(),error);out["ok"]=ok;if(!ok)out["error"]=error;sendJson(ok?200:400,out);}
  else{if(!in["enabled"].is<bool>()){web.send(400,"text/plain","enabled must be boolean");return;}mcpEnabled=in["enabled"];prefs.putBool("mcp",mcpEnabled);out["ok"]=true;sendJson(200,out);}};
 web.on("/api/wifi",HTTP_POST,config);web.on("/api/mcp",HTTP_POST,config);
 web.on("/mcp",HTTP_POST,[]{
  if(!mcpEnabled){web.send(503,"text/plain","MCP disabled");return;}
  if(!originOK()){web.send(403,"text/plain","Invalid Origin");return;}
  if(web.header("Authorization")!="Bearer "+token){web.send(401,"text/plain","Bearer token required");return;}
  JsonDocument in;if(web.arg("plain").length()>16384){web.send(413,"text/plain","Request too large");return;}
  if(deserializeJson(in,web.arg("plain"))){JsonDocument d;d["jsonrpc"]="2.0";d["id"]=nullptr;rpcError(d,-32700,"Parse error");sendJson(400,d);return;}
  if(!in.is<JsonObject>()||in["jsonrpc"]!="2.0"||!in["method"].is<String>()){JsonDocument d;d["jsonrpc"]="2.0";d["id"]=nullptr;rpcError(d,-32600,"Invalid Request");sendJson(400,d);return;}
  if(in["id"].isNull()){web.send(202,"text/plain","");return;}
  String v=web.header("MCP-Protocol-Version");if(v.length()&&v!=PROTOCOL){web.send(400,"text/plain","Unsupported MCP protocol version");return;}
  sendJson(200,rpc(in));
 });
 web.on("/mcp",HTTP_GET,[]{if(!originOK()){web.send(403,"text/plain","Invalid Origin");return;}web.sendHeader("Allow","POST");web.send(405,"text/plain","SSE stream not offered; use POST");});
 web.onNotFound([]{web.sendHeader("Location","http://"+(configAP?WiFi.softAPIP():WiFi.localIP()).toString()+"/");web.send(302,"text/plain","");});web.begin();

 JsonDocument boot;boot["event"]="boot";boot["firmware"]=VERSION;boot["sensor_mode"]=sensorEnabled?"sensor":"simulation";serialJson(boot);
}
void loop(){
 touchTick();
 if(scanBusy && (WiFi.scanComplete()>=0 || millis()-scanStartedAt>25000))scanBusy=false;
 web.handleClient();if(configAP)dns.processNextRequest();
 while(Serial.available()){char c=Serial.read();if(c=='\n'){if(serialLine.length())serialCommand(serialLine);serialLine="";}else if(c!='\r'){if(serialLine.length()<16384)serialLine+=c;else serialLine="";}}
 networkTick();
 discoveryTick();
 int state=WiFi.status();if(state!=lastWifi){lastWifi=state;JsonDocument d;d["event"]="wifi";d["status"]=state;d["ip"]=WiFi.localIP().toString();serialJson(d);}
 if(pressChannel>=0&&(int32_t)(millis()-pressUntil)>=0){pressChannel=-1;pressValue=0;Serial.println("{\"event\":\"simulated_release\"}");}
 delay(1);
}
