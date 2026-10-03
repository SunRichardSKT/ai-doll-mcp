#pragma once
static void addChannelTools(JsonArray tools){
 auto add=[&](const char* name,const char* description){JsonObject t=tools.add<JsonObject>();t["name"]=name;t["description"]=description;JsonObject s=t["inputSchema"].to<JsonObject>();s["type"]="object";s["properties"].to<JsonObject>();s["additionalProperties"]=false;return s;};
 add("get_channel_capabilities","Discover installed input/output types, drivers, free GPIOs and physical limits before configuring.");
 add("get_channel_config","Read persistent logical channel types, body labels, drivers, bindings and calibration. IDs independent of MUX ports.");
 add("read_channel_values","Read typed values with units, source, quality and age. Output readings report commanded state, not motor feedback.");
 JsonObject enable=add("set_input_enabled","Enable/disable installed physical input drivers without changing per-channel thresholds. Reboot defaults disabled; enable only after assembled hardware is confirmed.");enable["properties"]["enabled"]["type"]="boolean";enable["required"].to<JsonArray>().add("enabled");
 JsonObject s=add("set_channel_config","Atomically replace all 1..16 channels. Preserves historical labels/types; disables physical input and output after saving. pressure/temperature inputs; vibration output.");
 s["properties"]["schema_version"]["type"]="integer";s["properties"]["schema_version"]["const"]=1;
 JsonObject arr=s["properties"]["channels"].to<JsonObject>();arr["type"]="array";arr["minItems"]=1;arr["maxItems"]=16;
 JsonObject item=arr["items"].to<JsonObject>();item["type"]="object";item["additionalProperties"]=false;JsonObject p=item["properties"].to<JsonObject>();
 p["channel"]["type"]="integer";p["channel"]["minimum"]=0;p["channel"]["maximum"]=15;p["name"]["type"]="string";p["name"]["minLength"]=1;
 p["type"]["type"]="string";
 JsonArray types=p["type"]["enum"].to<JsonArray>();types.add("pressure");types.add("temperature");types.add("vibration");
 p["driver"]["type"]="string";JsonArray drivers=p["driver"]["enum"].to<JsonArray>();for(auto v:{"simulation","mux_adc","gpio_adc","gpio_pwm"})drivers.add(v);
 p["enabled"]["type"]="boolean";p["direction"]["type"]="string";JsonArray directions=p["direction"]["enum"].to<JsonArray>();directions.add("input");directions.add("output");
 p["mux_port"]["type"]="integer";p["mux_port"]["minimum"]=0;p["mux_port"]["maximum"]=7;p["gpio"]["type"]="integer";p["options"]["type"]="object";
 JsonArray required=item["required"].to<JsonArray>();for(auto k:{"channel","name","type","driver"})required.add(k);s["required"].to<JsonArray>().add("channels");
 s=add("simulate_channel_input","Inject pressure adc_raw (0 releases) or temperature degC/-40..125. millivolt temperature mode exercises NTC conversion/fault detection. Not a physical reading.");
 s["properties"]["channel"]["type"]="integer";s["properties"]["channel"]["minimum"]=0;s["properties"]["channel"]["maximum"]=15;s["properties"]["value"]["type"]="number";s["properties"]["unit"]["type"]="string";
 required=s["required"].to<JsonArray>();required.add("channel");required.add("value");
 s=add("set_output_enabled","Enable physical PWM only after user confirms external motor driver. Disabled on reboot/config changes. false stops all outputs. Simulation does not require arming.");
 s["properties"]["enabled"]["type"]="boolean";s["properties"]["external_driver_confirmed"]["type"]="boolean";s["required"].to<JsonArray>().add("enabled");
 s=add("set_vibration","Command an enabled vibration output 0..100 percent for 1..5000 ms, automatically stops; intensity=0 stops immediately. Never evidence of motor movement or touch.");
 s["properties"]["channel"]["type"]="integer";s["properties"]["channel"]["minimum"]=0;s["properties"]["channel"]["maximum"]=15;
 s["properties"]["intensity"]["type"]="integer";s["properties"]["intensity"]["minimum"]=0;s["properties"]["intensity"]["maximum"]=100;
 s["properties"]["duration_ms"]["type"]="integer";s["properties"]["duration_ms"]["minimum"]=1;s["properties"]["duration_ms"]["maximum"]=5000;
 required=s["required"].to<JsonArray>();for(auto k:{"channel","intensity","duration_ms"})required.add(k);
}
