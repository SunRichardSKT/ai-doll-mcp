#pragma once
#include "device_tools_asset.h"

// Static metadata is serialized directly from flash; dispatch remains in rpc().
static void listDeviceTools(JsonDocument &out){
 out["result"]["tools"]=serialized(reinterpret_cast<const char*>(DEVICE_TOOLS_JSON));
}
