#pragma once

enum class NetworkMode { SETUP, CONNECTING, NORMAL, RECOVERY };
static NetworkMode networkMode=NetworkMode::CONNECTING;
static bool configAP=false, allowConnect=true;
static uint32_t networkAttemptAt=0, ledOverrideUntil=0, buttonDownAt=0;
static bool buttonDown=false, buttonHandled=false;
static constexpr int SETUP_BUTTON_PIN=9; // SuperMini BOOT, active low. Do not hold during reset.
static const char* networkModeName(){
 switch(networkMode){case NetworkMode::SETUP:return "SETUP_MODE";case NetworkMode::NORMAL:return "NORMAL";case NetworkMode::RECOVERY:return "RECOVERY";default:return "CONNECTING";}
}
static void openConfigAP(NetworkMode mode){
 networkMode=mode;allowConnect=false;connectPending=false;
 WiFi.disconnect(false,false);WiFi.mode(WIFI_AP_STA);
 if(!configAP){WiFi.softAP(apName.c_str());dns.start(53,"*",WiFi.softAPIP());configAP=true;}
 ledOverrideUntil=0;
}
static void beginNetworkConnect(){
 allowConnect=true;networkAttemptAt=millis();lastAttempt=millis();
 networkMode=NetworkMode::CONNECTING;WiFi.disconnect(false,false);
 WiFi.begin(ssid.c_str(),password.c_str());
}
static void networkInit(){
 pinMode(SETUP_BUTTON_PIN,INPUT_PULLUP);
 WiFi.persistent(false);WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(false);
 if(ssid.isEmpty())openConfigAP(NetworkMode::SETUP);
 else {networkMode=NetworkMode::CONNECTING;connectPending=true;connectAt=millis()+500;networkAttemptAt=millis();}
}
static void networkTick(){
 uint32_t now=millis();
 bool held=digitalRead(SETUP_BUTTON_PIN)==LOW;
 if(held&&!buttonDown){buttonDown=true;buttonDownAt=now;buttonHandled=false;}
 if(!held){buttonDown=false;buttonHandled=false;}
 if(held&&!buttonHandled&&now-buttonDownAt>=3000){buttonHandled=true;openConfigAP(NetworkMode::SETUP);}
 if(connectPending&&(int32_t)(now-connectAt)>=0){connectPending=false;beginNetworkConnect();}
 if(allowConnect&&WiFi.status()==WL_CONNECTED){
  networkMode=NetworkMode::NORMAL;
  if(configAP){dns.stop();WiFi.softAPdisconnect(true);WiFi.mode(WIFI_STA);configAP=false;}
 }else if(networkMode==NetworkMode::NORMAL){
  networkMode=NetworkMode::CONNECTING;networkAttemptAt=now;lastAttempt=now;WiFi.reconnect();
 }else if(networkMode==NetworkMode::CONNECTING&&allowConnect&&!connectPending){
  if(now-networkAttemptAt>=60000)openConfigAP(NetworkMode::RECOVERY);
  else if(!scanBusy&&now-lastAttempt>=10000){WiFi.disconnect(false,false);WiFi.begin(ssid.c_str(),password.c_str());lastAttempt=now;}
 }
 // Explicit LED MCP test temporarily overrides indication for three seconds.
 if(ledOverrideUntil==0 || (int32_t)(now-ledOverrideUntil)>=0){
  ledOverrideUntil=0;
  bool on=networkMode==NetworkMode::NORMAL ? true : (now/(configAP?150:700))%2==0;
  setLed(on);
 }
}
