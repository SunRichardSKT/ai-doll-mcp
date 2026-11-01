#pragma once
#include <stdint.h>

// Unsigned millis wrap is supported; no persisted timers or automatic reopen.
struct SetupWindow {
 bool active=false,joined=false;
 uint32_t deadline=0;
 void open(uint32_t now){active=true;joined=false;deadline=now+600000U;}
 void close(){active=false;}
 uint32_t remaining(uint32_t now) const {return active&&(int32_t)(deadline-now)>0?deadline-now:0;}
 void connected(uint32_t now){if(active&&!joined){joined=true;if(remaining(now)>90000U)deadline=now+90000U;}}
};
static inline bool configurationAccessAllowed(bool window,bool onHotspot,bool paired,bool loginEnabled,bool loggedIn){
 return (window&&onHotspot)||(loginEnabled?loggedIn:paired);
}

// Keeping an AP alive must not turn normal LAN access into password recovery.
static inline bool configurationRecoveryAllowed(bool apActive,bool window,bool onHotspot){
 return apActive&&window&&onHotspot;
}
static inline bool otaNetworkAllowed(bool stationConnected,bool normal,bool onHotspot){
 return stationConnected&&normal&&!onHotspot;
}
static inline bool uplinkNetworkAllowed(bool stationConnected,bool normal){
 return stationConnected&&normal;
}

// One bounded connection attempt at a time. Radio resets never clear credentials.
struct NetworkRecovery {
 enum Action { NONE, CONNECT, RESTART_RADIO };
 bool offline=false,inFlight=false;
 uint32_t since=0,started=0,next=0,attempts=0,resets=0;
 void connected(){offline=false;inFlight=false;attempts=0;}
 void lost(uint32_t now){if(!offline){offline=true;since=now;attempts=0;inFlight=false;next=now+2000U;}}
 void begin(uint32_t now){lost(now);inFlight=true;started=now;attempts++;}
 Action poll(uint32_t now){
  if(!offline)return NONE;
  if(inFlight){
   if(now-started<30000U)return NONE;
   inFlight=false;
   const uint32_t delays[]={2000,5000,10000,30000,60000};
   next=now+delays[attempts<5?attempts-1:4];return NONE;
  }
  if((int32_t)(now-next)<0)return NONE;
  return attempts&&attempts%3==0?RESTART_RADIO:CONNECT;
 }
 bool recovering(uint32_t now)const{return offline&&now-since>=60000U;}
 uint32_t waitMs(uint32_t now)const{
  if(!offline)return 0;
  uint32_t at=inFlight?started+30000U:next;
  return (int32_t)(at-now)>0?at-now:0;
 }
};
