"""Compile production network state against a radio/button double; no physical board."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
class HotspotPolicyTests(unittest.TestCase):
    def test_actual_state_machine_and_access_policy(self):
        source=r'''
#include <string>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
struct String:std::string {using std::string::string;String(std::string s):std::string(s){} bool isEmpty()const{return empty();}};
static String operator+(const String&a,const char*b){return String(std::string(a)+b);}
static String operator+(const char*a,const String&b){return String(a+std::string(b));}
struct IPAddress {int a=0;IPAddress(){} IPAddress(int b,int,int,int):a(b){} bool operator!=(IPAddress b)const{return a!=b.a;}bool operator==(IPAddress b)const{return a==b.a;}};
static uint32_t clockNow=0;static bool pressed=false;uint32_t millis(){return clockNow;}
enum{INPUT_PULLUP,LOW,HIGH,WL_CONNECTED=3,WIFI_STA=1,WIFI_AP=2,WIFI_AP_STA=3,ARDUINO_EVENT_WIFI_STA_START=1,ARDUINO_EVENT_WIFI_AP_START=2,ARDUINO_EVENT_WIFI_STA_DISCONNECTED=3,ARDUINO_EVENT_WIFI_AP_STOP=4};
using wifi_power_t=int;static constexpr int WIFI_POWER_8_5dBm=34,WIFI_POWER_19_5dBm=78;
using arduino_event_id_t=int;struct arduino_event_info_t {struct {int reason;}wifi_sta_disconnected;};
void pinMode(int,int){}int digitalRead(int){return pressed?LOW:HIGH;}void setLed(bool){}
struct {uint64_t getEfuseMac(){return 0x112233445566;}}ESP;
struct {void end(){}bool begin(const char*){return true;}void addService(const char*,const char*,int){}void addServiceTxt(const char*,const char*,const char*,String){}}MDNS;
struct Radio {bool online=false,failAP=false,ap=false;int modes=WIFI_STA,starts=0,disconnects=0,joins=0;
 String currentSSID;String SSID(){return currentSSID;}
 int status(){return online?WL_CONNECTED:0;}IPAddress localIP(){return online?IPAddress(10,0,0,2):IPAddress();}
 void onEvent(void(*)(int,arduino_event_info_t)){} void setSleep(bool){}void persistent(bool){}void setAutoReconnect(bool){}
 bool mode(int m){modes=m;ap=(m&WIFI_AP)!=0;return true;}bool setTxPower(int){return true;}int getTxPower(){return 34;}
 void disconnect(bool,bool){online=false;disconnects++;}bool softAPConfig(IPAddress,IPAddress,IPAddress){return true;}
 String softAPSSID(){return ap?String("test-doll"):String("");}IPAddress softAPIP(){return ap?IPAddress(192,168,4,1):IPAddress();}
 bool softAP(const char*,const char*,int,int,int){starts++;ap=!failAP;return ap;}
 void softAPdisconnect(bool){ap=false;}void setHostname(const char*){}void begin(const char* ssid,const char*){currentSSID=ssid;joins++;}void reconnect(){joins++;}
}WiFi;
struct {void stop(){}void start(int,const char*,IPAddress){}}dns;
struct {String getString(const char*,const char* d){return String(d);}}prefs;
struct JsonVariantConst {JsonVariantConst operator[](const char*)const{return {};};bool isNull()const{return true;}template<class T>bool is()const{return false;}template<class T>T as()const{return T();}};
struct Field {template<class T>void operator=(T){}};struct JsonObject {Field operator[](const char*){return {};}};
static String ssid,password,deviceName="test-doll",apName="test-id";static bool connectPending=false,scanBusy=false;static uint32_t connectAt=0,lastAttempt=0;
#include "network_state.h"
void tick(uint32_t now){clockNow=now;networkTick();}
int main(){
 for(int window=0;window<2;window++)for(int ap=0;ap<2;ap++)for(int paired=0;paired<2;paired++)for(int login=0;login<2;login++)for(int logged=0;logged<2;logged++)
  assert(configurationAccessAllowed(window,ap,paired,login,logged)==((window&&ap)||(login?logged:paired)));
 // Saved Wi-Fi: no AP on boot, failure, or eventual automatic recovery.
 ssid="home";networkInit();assert(!configAP&&!setupWindow.active);tick(600);assert(WiFi.joins==1);
 tick(61000);assert(networkMode==NetworkMode::RECOVERY&&!configAP);int joins=WiFi.joins;tick(72000);assert(WiFi.joins>joins&&!configAP);
 WiFi.online=true;tick(73000);assert(networkMode==NetworkMode::NORMAL);
 // Explicit BOOT: keep the connected station and a full ten-minute window.
 int disconnects=WiFi.disconnects;pressed=true;tick(74000);tick(77001);pressed=false;tick(77002);
 assert(configAP&&networkMode==NetworkMode::NORMAL&&WiFi.online&&WiFi.disconnects==disconnects);
 assert(setupWindow.remaining(clockNow)>599000);tick(677002);assert(!configAP&&WiFi.online);int starts=WiFi.starts;tick(800000);assert(WiFi.starts==starts);
 // Blank install: bounded AP. Provisioning joins STA without prematurely closing AP.
 ssid="";WiFi.online=false;clockNow=900000;networkInit();assert(configAP&&!allowConnect);assert(setupWindow.remaining(clockNow)==600000);
 ssid="new-home";setupWindow.joined=false;beginNetworkConnect();assert(configAP&&WiFi.modes==WIFI_AP_STA);
 WiFi.online=true;tick(901000);assert(setupWindow.remaining(clockNow)==90000);tick(990999);assert(configAP);tick(991000);assert(!configAP&&WiFi.online);
 // AP start failures retry only within the original deadline.
 ssid="";WiFi.online=false;WiFi.failAP=true;clockNow=1100000;openConfigAP(NetworkMode::SETUP);starts=WiFi.starts;tick(1105001);assert(WiFi.starts==starts+1);tick(1700000);assert(!setupWindow.active);starts=WiFi.starts;tick(1710000);assert(WiFi.starts==starts);
 // millis wrap cannot turn ten minutes into an unlimited window.
 SetupWindow w;w.open(0xffff0000U);assert(w.remaining(0xffff0000U)==600000);assert(w.remaining(uint32_t(0xffff0000U+600000U))==0);
 w.open(0);w.connected(1000);w.connected(80000);assert(w.deadline==91000);w.close();assert(!w.remaining(80000));
 // Changing Wi-Fi while online: the old station is not success for the new target.
 ssid="old-home";WiFi.currentSSID=ssid;WiFi.online=true;WiFi.failAP=false;clockNow=2000000;
 openConfigAP(NetworkMode::NORMAL);setupWindow.joined=false;ssid="wrong-new-home";
 connectPending=true;connectAt=clockNow+500;tick(2000001);
 assert(setupWindow.remaining(clockNow)==599999);
 tick(2000500);assert(!WiFi.online);tick(2090002);assert(configAP&&setupWindow.active);
 // A late callback for the old target still must not start the grace timer.
 WiFi.online=true;WiFi.currentSSID="old-home";tick(2090003);assert(!setupWindow.joined);
 WiFi.currentSSID=ssid;tick(2090004);assert(setupWindow.remaining(clockNow)==90000);
 tick(2180004);assert(!configAP&&WiFi.online);
}
'''
        with tempfile.TemporaryDirectory(prefix='aidoll-hotspot-') as folder:
            out=Path(folder)
            (out/'ESPmDNS.h').write_text('#pragma once\n')
            for name in ('network_policy.h','network_state.h'):
                shutil.copyfile(ROOT/'firmware/src'/name,out/name)
            (out/'state.cpp').write_text(source,encoding='utf-8')
            result=subprocess.run(['g++','-std=c++11','-Wno-unused-function','-I',str(out),str(out/'state.cpp'),'-o',str(out/'state.exe')],capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(out/'state.exe')],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
