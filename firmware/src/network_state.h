#pragma once
#include <ESPmDNS.h>
#include "network_policy.h"

// Hardware-derived name stays the same across DHCP leases and display-name edits.
static String deviceHostname(){
 char suffix[13];uint64_t mac=ESP.getEfuseMac();
 snprintf(suffix,sizeof(suffix),"%04x%08lx",(unsigned int)(mac>>32),(unsigned long)(mac&0xffffffff));
 return String("ai-doll-")+suffix;
}
static bool mdnsActive=false;
static IPAddress mdnsAddress;
static uint32_t mdnsAttemptAt=0;
static void deviceNameTick(){
 IPAddress address=WiFi.localIP();
 bool online=WiFi.status()==WL_CONNECTED&&address!=IPAddress(0,0,0,0);
 if(mdnsActive&&(!online||address!=mdnsAddress)){MDNS.end();mdnsActive=false;}
 if(!online||mdnsActive||millis()-mdnsAttemptAt<5000)return;
 mdnsAttemptAt=millis();mdnsActive=MDNS.begin(deviceHostname().c_str());
 if(mdnsActive){mdnsAddress=address;MDNS.addService("http","tcp",80);
  MDNS.addServiceTxt("http","tcp","device_id",apName);}
}

enum class NetworkMode { SETUP, CONNECTING, NORMAL, RECOVERY };
static NetworkMode networkMode=NetworkMode::CONNECTING;
static bool configAP=false, allowConnect=true;
static SetupWindow setupWindow;
static String setupAPPassword;
static uint32_t closeSetupAt=0;
static String apStartError;
static uint32_t apLastAttempt=0,apStartAttempts=0;
static volatile int lastRadioEvent=-1,lastDisconnectReason=0;
static volatile bool apRadioStarted=false;
static constexpr int SETUP_AP_CHANNEL=1;
static constexpr wifi_power_t SUPERMINI_TX_POWER=WIFI_POWER_8_5dBm;
static void radioEvent(arduino_event_id_t event,arduino_event_info_t info){
 lastRadioEvent=(int)event;
 // This assembled SuperMini failed authentication/beacon visibility at 20dBm,
 // while 8.5dBm passed actual STA and AP tests. Apply again after each radio start.
 if(event==ARDUINO_EVENT_WIFI_STA_START||event==ARDUINO_EVENT_WIFI_AP_START)WiFi.setTxPower(SUPERMINI_TX_POWER);
 if(event==ARDUINO_EVENT_WIFI_STA_DISCONNECTED)lastDisconnectReason=(int)info.wifi_sta_disconnected.reason;
 if(event==ARDUINO_EVENT_WIFI_AP_START)apRadioStarted=true;
 if(event==ARDUINO_EVENT_WIFI_AP_STOP)apRadioStarted=false;
}
static uint32_t ledOverrideUntil=0, buttonDownAt=0;
static NetworkRecovery connectionRecovery;
static bool networkReady(){return !connectPending&&WiFi.status()==WL_CONNECTED&&WiFi.localIP()!=IPAddress(0,0,0,0)&&WiFi.SSID()==ssid;}
static bool buttonDown=false, buttonHandled=false;
static constexpr int SETUP_BUTTON_PIN=9; // SuperMini BOOT, active low. Do not hold during reset.
static const char* networkModeName(){
 switch(networkMode){case NetworkMode::SETUP:return "SETUP_MODE";case NetworkMode::NORMAL:return "NORMAL";case NetworkMode::RECOVERY:return "RECOVERY";default:return "CONNECTING";}
}
static void closeConfigAP(){
 setupWindow.close();closeSetupAt=0;dns.stop();WiFi.softAPdisconnect(true);configAP=false;
 WiFi.mode(WIFI_STA);allowConnect=!ssid.isEmpty();
 if(!allowConnect)networkMode=NetworkMode::SETUP;
}
static void startConfigAP(){
 apLastAttempt=millis();apStartAttempts++;dns.stop();configAP=false;
 bool online=WiFi.status()==WL_CONNECTED;
 bool radio=WiFi.mode((online||!ssid.isEmpty())?WIFI_AP_STA:WIFI_AP);
 bool address=radio&&WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0));
 bool opened=address&&WiFi.softAP(deviceName.c_str(),setupAPPassword.isEmpty()?nullptr:setupAPPassword.c_str(),SETUP_AP_CHANNEL,0,4);
 configAP=opened&&WiFi.softAPSSID()==deviceName&&WiFi.softAPIP()==IPAddress(192,168,4,1);
 apStartError=configAP?"":!radio?"wifi_mode_failed":!address?"ap_ip_failed":!opened?"softap_start_failed":"ap_configuration_mismatch";
 if(configAP)dns.start(53,"*",WiFi.softAPIP());
}
static void openConfigAP(NetworkMode mode){
 setupWindow.open(millis());closeSetupAt=0;startConfigAP();
 bool online=WiFi.status()==WL_CONNECTED;setupWindow.joined=online;
 networkMode=online?NetworkMode::NORMAL:mode;allowConnect=!ssid.isEmpty();
 if(allowConnect&&!online){connectPending=true;connectAt=millis()+500;}
 ledOverrideUntil=0;
}
static void beginNetworkConnect(){
 allowConnect=true;connectionRecovery.begin(millis());
 networkMode=connectionRecovery.recovering(millis())?NetworkMode::RECOVERY:NetworkMode::CONNECTING;WiFi.disconnect(false,false);
 WiFi.mode(configAP?WIFI_AP_STA:WIFI_STA);
 WiFi.setHostname(deviceHostname().c_str());
 WiFi.begin(ssid.c_str(),password.c_str());
}
static void networkInit(){
 connectionRecovery=NetworkRecovery();
 pinMode(SETUP_BUTTON_PIN,INPUT_PULLUP);
 WiFi.onEvent(radioEvent);WiFi.setSleep(false);
 WiFi.persistent(false);WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(false);
 setupAPPassword=prefs.getString("setup_psk","");
 if(ssid.isEmpty())openConfigAP(NetworkMode::SETUP);
 if(!ssid.isEmpty()){networkMode=NetworkMode::CONNECTING;allowConnect=true;connectPending=true;connectAt=millis()+500;}
}
static void networkTick(){
 uint32_t now=millis();
 if((setupWindow.active&&!setupWindow.remaining(now))||(closeSetupAt&&(int32_t)(now-closeSetupAt)>=0))closeConfigAP();
 if(setupWindow.active&&!configAP&&now-apLastAttempt>=5000)startConfigAP();
 bool held=digitalRead(SETUP_BUTTON_PIN)==LOW;
 if(held&&!buttonDown){buttonDown=true;buttonDownAt=now;buttonHandled=false;}
 if(!held){buttonDown=false;buttonHandled=false;}
 if(held&&!buttonHandled&&now-buttonDownAt>=3000){buttonHandled=true;openConfigAP(NetworkMode::SETUP);}
 if(connectPending&&(int32_t)(now-connectAt)>=0){connectPending=false;beginNetworkConnect();}
 // A new target must obtain an address; an old association is not success.
 if(allowConnect&&!connectPending){
  if(networkReady()){
   connectionRecovery.connected();networkMode=NetworkMode::NORMAL;setupWindow.connected(now);
  }else{
   connectionRecovery.lost(now);
   networkMode=connectionRecovery.recovering(now)?NetworkMode::RECOVERY:NetworkMode::CONNECTING;
   if(!scanBusy){
    auto action=connectionRecovery.poll(now);
    if(action==NetworkRecovery::RESTART_RADIO){
     if(mdnsActive){MDNS.end();mdnsActive=false;}
     WiFi.disconnect(false,false);WiFi.mode(WIFI_OFF);configAP=false;connectionRecovery.resets++;
     if(setupWindow.active&&setupWindow.remaining(now))startConfigAP();
    }
    if(action!=NetworkRecovery::NONE)beginNetworkConnect();
   }
  }
 }
 // Explicit LED MCP test temporarily overrides indication for three seconds.
 if(ledOverrideUntil==0 || (int32_t)(now-ledOverrideUntil)>=0){
  ledOverrideUntil=0;
  bool on=configAP ? (now/150)%2==0 : networkMode==NetworkMode::NORMAL ? true : (now/700)%2==0;
  setLed(on);
 }
 deviceNameTick();
}
