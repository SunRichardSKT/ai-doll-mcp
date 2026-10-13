#pragma once

// Keeping an AP alive must not turn normal LAN access into password recovery.
static inline bool configurationRecoveryAllowed(bool apActive,bool normal,bool onHotspot){
 return apActive&&!normal&&onHotspot;
}
static inline bool otaNetworkAllowed(bool stationConnected,bool normal,bool onHotspot){
 return stationConnected&&normal&&!onHotspot;
}
static inline bool uplinkNetworkAllowed(bool stationConnected,bool normal){
 return stationConnected&&normal;
}
