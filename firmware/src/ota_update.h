#pragma once
#include <esp_ota_ops.h>
#include <esp_app_format.h>
#include <mbedtls/base64.h>
#include <mbedtls/sha256.h>

// Arduino otherwise confirms a pending image before our setup has run.
extern "C" bool verifyRollbackLater(){return true;}
static bool otaActive=false,otaWriting=false,otaCommitted=false,otaVerified=false;
static wifi_ps_type_t otaSavedSleep=WIFI_PS_MIN_MODEM;
static esp_ota_handle_t otaHandle=0;
static const esp_partition_t* otaPartition=nullptr;
static uint32_t otaSize=0,otaReceived=0,otaLast=0,otaRebootAt=0;
static uint32_t otaHealthyLoops=0;
static String otaTicket,otaExpected,otaError;
static mbedtls_sha256_context otaHash;
static uint8_t otaBuffer[3072];

static void otaAbort(const String &reason){
 if(otaWriting)esp_ota_abort(otaHandle);
 if(otaActive){mbedtls_sha256_free(&otaHash);WiFi.setSleep(otaSavedSleep);}
 otaActive=false;otaWriting=false;otaTicket="";otaError=reason;
}
static void otaStatus(JsonObject out){
 const auto* running=esp_ota_get_running_partition();
 const auto* next=esp_ota_get_next_update_partition(nullptr);
 esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
 if(running)esp_ota_get_state_partition(running,&state);
 out["supported"]=next!=nullptr;out["active"]=otaActive;out["committed"]=otaCommitted;
 out["received_bytes"]=otaReceived;out["expected_bytes"]=otaSize;out["error"]=otaError;
 out["running_partition"]=running?running->label:"";out["capacity_bytes"]=next?next->size:0;
 out["pending_verification"]=state==ESP_OTA_IMG_PENDING_VERIFY;
 out["rollback_configured"]=true;out["confirmation_after_ms"]=30000;
 out["chunk_bytes"]=sizeof(otaBuffer);out["idle_timeout_ms"]=30000;
}
static bool otaAuthorized(){
 // Never inherit the password-free provisioning portal's admin bypass.
 if(configAP||WiFi.status()!=WL_CONNECTED||!originOK()||
    !web.authenticate("admin",apPass.c_str())||web.header("X-Setup-Token")!=token){
  web.send(403,"application/json","{\"error\":\"OTA requires LAN admin authentication and setup token\"}");return false;
 }
 return true;
}
static void otaRequest(){
 if(!otaAuthorized())return;
 JsonDocument in,out;
 if(web.arg("plain").length()>5000||deserializeJson(in,web.arg("plain"))||!in.is<JsonObject>()){
  web.send(400,"application/json","{\"error\":\"Invalid OTA JSON\"}");return;
 }
 String action=in["action"]|"";
 auto fail=[&](int code,const char* reason){out["error"]=reason;sendJson(code,out);};
 if(action=="start"){
  if(otaActive||otaCommitted){fail(409,"Upgrade already active");return;}
  if(!in["confirmed"].is<bool>()||!in["confirmed"].as<bool>()||in["target"]!="ai-doll-supermini-v1"||in["chip"]!="esp32c3"){
   fail(400,"Explicit confirmation and matching target/chip required");return;
  }
  otaPartition=esp_ota_get_next_update_partition(nullptr);
  esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
  esp_ota_get_state_partition(esp_ota_get_running_partition(),&state);
  if(state==ESP_OTA_IMG_PENDING_VERIFY){fail(409,"Wait for current boot verification");return;}
  if(!otaPartition||!in["bytes"].is<uint32_t>()||in["bytes"].as<uint32_t>()<288||in["bytes"].as<uint32_t>()>otaPartition->size){fail(400,"Invalid application size");return;}
  String sha=in["sha256"]|"";
  if(sha.length()!=64){fail(400,"SHA-256 required");return;}
  for(char c:sha)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f'))){fail(400,"Lowercase SHA-256 required");return;}
  for(const auto &s:touches)if(s.active){fail(409,"Release active pressure inputs before upgrading");return;}
  if(calibration.capturing){fail(409,"Finish or cancel calibration first");return;}
  disarmOutputs();otaSize=in["bytes"];otaReceived=0;otaExpected=sha;otaError="";
  otaTicket=randomHex();otaLast=millis();otaActive=true;
  otaSavedSleep=WiFi.getSleep();WiFi.setSleep(false);
  mbedtls_sha256_init(&otaHash);mbedtls_sha256_starts_ret(&otaHash,0);
  out["ticket"]=otaTicket;out["chunk_bytes"]=sizeof(otaBuffer);sendJson(200,out);return;
 }
 if(!otaActive||!in["ticket"].is<String>()||in["ticket"].as<String>()!=otaTicket){fail(409,"Invalid or expired OTA ticket");return;}
 if(action=="abort"){otaAbort("Cancelled");out["ok"]=true;sendJson(200,out);return;}
 if(action=="chunk"){
  if(!in["offset"].is<uint32_t>()||in["offset"].as<uint32_t>()!=otaReceived){fail(409,"Chunk offset mismatch; do not blindly retry");return;}
  String data=in["data"]|"";size_t length=0;
  if(data.isEmpty()||data.length()>4096||mbedtls_base64_decode(otaBuffer,sizeof(otaBuffer),&length,(const unsigned char*)data.c_str(),data.length())||!length||length>otaSize-otaReceived){fail(400,"Invalid chunk length or encoding");return;}
  if(!otaReceived){
   // Check chip and app descriptor before erasing the inactive slot.
   esp_image_header_t header;esp_app_desc_t app;
   if(length<sizeof(header)+sizeof(esp_image_segment_header_t)+sizeof(app)){fail(400,"First chunk must contain app header");return;}
   memcpy(&header,otaBuffer,sizeof(header));memcpy(&app,otaBuffer+sizeof(header)+sizeof(esp_image_segment_header_t),sizeof(app));
   esp_app_desc_t current;esp_ota_get_partition_description(esp_ota_get_running_partition(),&current);
   if(header.magic!=ESP_IMAGE_HEADER_MAGIC||header.chip_id!=ESP_CHIP_ID_ESP32C3||app.magic_word!=ESP_APP_DESC_MAGIC_WORD||memcmp(app.project_name,current.project_name,sizeof(app.project_name))){
    otaAbort("Wrong chip or application header");fail(400,"Wrong chip or application header");return;
   }
   esp_err_t err=esp_ota_begin(otaPartition,otaSize,&otaHandle);
   if(err!=ESP_OK){otaAbort("OTA begin failed");fail(500,"OTA begin failed");return;}
   otaWriting=true;
  }
  if(esp_ota_write(otaHandle,otaBuffer,length)!=ESP_OK){otaAbort("Flash write failed");fail(500,"Flash write failed");return;}
  mbedtls_sha256_update_ret(&otaHash,otaBuffer,length);otaReceived+=length;otaLast=millis();
  out["received_bytes"]=otaReceived;sendJson(200,out);return;
 }
 if(action=="finish"){
  if(otaReceived!=otaSize){fail(409,"Incomplete image");return;}
  uint8_t digest[32];mbedtls_sha256_finish_ret(&otaHash,digest);char hex[65];
  for(int i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",digest[i]);
  if(otaExpected!=hex){otaAbort("SHA-256 mismatch");fail(400,"SHA-256 mismatch");return;}
  esp_err_t err=esp_ota_end(otaHandle);otaWriting=false;
  if(err!=ESP_OK){otaAbort("Image validation failed");fail(400,"Image validation failed");return;}
  if(esp_ota_set_boot_partition(otaPartition)!=ESP_OK){otaAbort("Boot selection failed");fail(500,"Boot selection failed");return;}
  otaAbort("");otaCommitted=true;otaRebootAt=millis()+1200;
  out["ok"]=true;out["rebooting"]=true;sendJson(200,out);return;
 }
 fail(400,"Unknown OTA action");
}
static void otaTick(){
 if(otaHealthyLoops<1000)otaHealthyLoops++;
 if(otaActive&&(uint32_t)(millis()-otaLast)>30000)otaAbort("Upload timeout; previous firmware retained");
 if(otaCommitted&&(int32_t)(millis()-otaRebootAt)>=0)ESP.restart();
 if(!otaVerified&&otaHealthyLoops>=1000&&millis()>=30000&&ESP.getFreeHeap()>32768){
  esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
  esp_ota_get_state_partition(esp_ota_get_running_partition(),&state);
  if(state!=ESP_OTA_IMG_PENDING_VERIFY||esp_ota_mark_app_valid_cancel_rollback()==ESP_OK)otaVerified=true;
 }
}
