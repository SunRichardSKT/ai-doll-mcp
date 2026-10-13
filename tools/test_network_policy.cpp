#include "../firmware/src/network_policy.h"
#include <cassert>
int main(){
 // Normal operation with a persistent hotspot never bypasses configured login.
 assert(!configurationRecoveryAllowed(true,true,true));
 assert(!configurationRecoveryAllowed(true,true,false));
 // Manual recovery is allowed only on the directly connected hotspot.
 assert(configurationRecoveryAllowed(true,false,true));
 assert(!configurationRecoveryAllowed(true,false,false));
 assert(!configurationRecoveryAllowed(false,false,true));
 // OTA is still available on the normal LAN, and never on the hotspot.
 assert(otaNetworkAllowed(true,true,false));
 assert(!otaNetworkAllowed(true,true,true));
 assert(!otaNetworkAllowed(true,false,false));
 assert(!otaNetworkAllowed(false,true,false));
 // A persistent AP does not disable normal upstream delivery.
 assert(uplinkNetworkAllowed(true,true));
 assert(!uplinkNetworkAllowed(true,false));
 assert(!uplinkNetworkAllowed(false,true));
}
