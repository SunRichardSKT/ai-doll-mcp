#include "../firmware/src/network_policy.h"
#include <cassert>
int main(){
 // Login recovery requires an active window and the directly connected hotspot.
 assert(configurationRecoveryAllowed(true,true,true));
 assert(!configurationRecoveryAllowed(true,true,false));
 // An expired or unopened window cannot grant recovery.
 assert(!configurationRecoveryAllowed(true,false,true));
 assert(!configurationRecoveryAllowed(true,false,false));
 assert(!configurationRecoveryAllowed(false,false,true));
 // OTA is still available on the normal LAN, and never on the hotspot.
 assert(otaNetworkAllowed(true,true,false));
 assert(!otaNetworkAllowed(true,true,true));
 assert(!otaNetworkAllowed(true,false,false));
 assert(!otaNetworkAllowed(false,true,false));
 // A temporary AP does not disable normal upstream delivery.
 assert(uplinkNetworkAllowed(true,true));
 assert(!uplinkNetworkAllowed(true,false));
 assert(!uplinkNetworkAllowed(false,true));
}
