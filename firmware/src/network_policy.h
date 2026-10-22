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
