#pragma once
#include <esp_http_client.h>
#include <esp_tls.h>
// Arduino also ships a header with this name for its separate bundle. Use the
// IDF bundle enabled in this board's sdkconfig, linked by esp_http_client.
extern "C" esp_err_t esp_crt_bundle_attach(void *conf);
#include <freertos/queue.h>

// Only the network worker touches HTTP/TLS. All sensors, Preferences, filesystem,
// RPC and acknowledgements remain on Arduino's loop task.
static bool remoteEnabled=false,remoteLocalHTTP=false,remotePending=false,remoteWorkerReady=false;
static String remoteURL,remoteToken,remoteCA,remoteError,remoteResult;
static String remoteLastCommand;
static uint32_t remoteGeneration=0,remoteNextAt=0,remoteLastOK=0,remoteAfter=0;
static uint32_t remoteFailures=0,remoteObservedSeq=0;
static int remoteHTTPCode=0;
static QueueHandle_t remoteJobs=nullptr,remoteResponses=nullptr;
struct RemoteJob {
 String url,token,ca,body,response,error,boot,epoch;
 uint32_t generation=0;uint64_t cursor=0;int code=0,tlsCode=0,tlsFlags=0;
};

static bool remotePrivateHost(const String &host){
 IPAddress ip;if(!ip.fromString(host))return false;
 return ip[0]==10||(ip[0]==172&&ip[1]>=16&&ip[1]<=31)||(ip[0]==192&&ip[1]==168);
}
static bool remoteValidateURL(String &url,bool local,String &error){
 while(url.endsWith("/"))url.remove(url.length()-1);
 bool tls=url.startsWith("https://"),plain=url.startsWith("http://");
 int start=tls?8:7;
 if((!tls&&!plain)||url.length()>240){error="请输入完整 HTTPS 服务器地址";return false;}
 String authority=url.substring(start),host=authority;
 if(authority.isEmpty()||authority.indexOf('/')>=0||authority.indexOf('@')>=0||
    authority.indexOf('?')>=0||authority.indexOf('#')>=0||authority.indexOf(' ')>=0||authority.indexOf('\\')>=0){
  error="服务器地址只包含协议、主机和可选端口";return false;
 }
 int colon=authority.indexOf(':');
 if(colon>=0){
  host=authority.substring(0,colon);String port=authority.substring(colon+1);
  for(size_t i=0;i<port.length();i++)if(port[i]<'0'||port[i]>'9'){error="端口无效";return false;}
  if(port.isEmpty()||port.toInt()<1||port.toInt()>65535){error="端口无效";return false;}
 }
 if(host.isEmpty()){error="主机无效";return false;}
 if(plain&&(!local||!remotePrivateHost(host))){error="HTTP 仅允许明确勾选的局域网 IP；远程服务器请用 HTTPS";return false;}
 return true;
}
static void remoteConfigView(JsonObject out){
 out["enabled"]=remoteEnabled;out["server_url"]=remoteURL;out["local_http"]=remoteLocalHTTP;
 out["token_saved"]=!remoteToken.isEmpty();out["custom_ca_saved"]=!remoteCA.isEmpty();
}
static void remoteStatus(JsonObject out){
 remoteConfigView(out);out["uploading"]=remotePending;out["last_http_status"]=remoteHTTPCode;
 out["last_success_uptime_ms"]=remoteLastOK;out["consecutive_failures"]=remoteFailures;
 out["error"]=remoteError;out["connected"]=remoteEnabled&&remoteLastOK>0&&millis()-remoteLastOK<15000;
 out["mode"]=remoteEnabled?"device_push":"local_bridge";
}
static bool remoteSave(JsonVariantConst value,String &error){
 if(otaActive||otaCommitted){error="升级进行中";return false;}
 if(!value["enabled"].is<bool>()){error="enabled 必须为布尔值";return false;}
 bool enabled=value["enabled"].as<bool>(),local=value["local_http"]|false;
 if(enabled&&!remoteWorkerReady){error="worker_unavailable";return false;}
 String url=value["server_url"]|remoteURL,secret=value["device_token"]|"",ca=value["root_ca"]|remoteCA;
 if(secret.isEmpty())secret=remoteToken;
 if(enabled&&!remoteValidateURL(url,local,error))return false;
 if(enabled&&(secret.length()!=64)){error="请填写服务器生成的 64 位设备连接令牌";return false;}
 for(size_t i=0;i<secret.length();i++)if(!isxdigit((unsigned char)secret[i])){error="令牌无效";return false;}
 if(ca.length()>6000||(!ca.isEmpty()&&(!ca.startsWith("-----BEGIN CERTIFICATE-----")||ca.indexOf("-----END CERTIFICATE-----")<0))){error="根证书必须为 PEM 格式（最多 6000 字节）";return false;}
 JsonDocument saved;saved["enabled"]=enabled;saved["server_url"]=url;saved["device_token"]=secret;saved["local_http"]=local;saved["root_ca"]=ca;
 String wire=encode(saved);if(prefs.putString("uplink",wire)!=wire.length()){error="配置保存失败";return false;}
 bool changed=url!=remoteURL||secret!=remoteToken;
 remoteEnabled=enabled;remoteLocalHTTP=local;remoteURL=url;remoteToken=secret;remoteCA=ca;
 remoteGeneration++;remoteNextAt=0;remoteLastOK=0;remoteFailures=0;remoteError="";
 if(changed){remoteAfter=0;remoteResult="";remoteLastCommand="";}
 return true;
}
static esp_err_t remoteHTTPEvent(esp_http_client_event_t *event){
 RemoteJob *job=(RemoteJob*)event->user_data;
 if(event->event_id==HTTP_EVENT_DISCONNECTED&&event->data){
  esp_tls_get_and_clear_last_error((esp_tls_error_handle_t)event->data,&job->tlsCode,&job->tlsFlags);
 }
 if(event->event_id==HTTP_EVENT_ON_DATA&&event->data_len){
  if(job->response.length()+event->data_len>24576){job->error="response_too_large";return ESP_FAIL;}
  job->response.concat((const char*)event->data,event->data_len);
 }
 return ESP_OK;
}
static void remoteWorker(void*){
 for(;;){
  RemoteJob *job=nullptr;if(xQueueReceive(remoteJobs,&job,portMAX_DELAY)!=pdTRUE)continue;
  esp_http_client_config_t cfg={};cfg.url=job->url.c_str();cfg.timeout_ms=4000;
  cfg.event_handler=remoteHTTPEvent;cfg.user_data=job;cfg.disable_auto_redirect=true;
  if(job->url.startsWith("https://")){
   if(!job->ca.isEmpty())cfg.cert_pem=job->ca.c_str();else cfg.crt_bundle_attach=esp_crt_bundle_attach;
  }
  esp_http_client_handle_t client=esp_http_client_init(&cfg);
  if(client){
   esp_http_client_set_method(client,HTTP_METHOD_POST);
   esp_http_client_set_header(client,"Content-Type","application/json");
   String auth="Bearer "+job->token;esp_http_client_set_header(client,"Authorization",auth.c_str());
   esp_http_client_set_post_field(client,job->body.c_str(),job->body.length());
   esp_err_t result=esp_http_client_perform(client);job->code=esp_http_client_get_status_code(client);
   if(result!=ESP_OK&&job->error.isEmpty()){
    job->error=String("http_transport_")+String((int)result)+"_tls_"+String(job->tlsCode)+"_flags_"+String(job->tlsFlags);
   }
   esp_http_client_cleanup(client);
  }else job->error="http_init_failed";
  job->body="";job->token="";job->ca="";
  if(xQueueSend(remoteResponses,&job,portMAX_DELAY)!=pdTRUE)delete job;
 }
}
static void remoteInit(){
 JsonDocument stored;if(!deserializeJson(stored,prefs.getString("uplink","{}"))){
  remoteEnabled=stored["enabled"]|false;remoteLocalHTTP=stored["local_http"]|false;
  remoteURL=stored["server_url"]|"";remoteToken=stored["device_token"]|"";remoteCA=stored["root_ca"]|"";
 }
 String error;if(remoteEnabled&&(!remoteValidateURL(remoteURL,remoteLocalHTTP,error)||remoteToken.length()!=64)){remoteEnabled=false;remoteError="stored_configuration_invalid";}
 remoteJobs=xQueueCreate(1,sizeof(RemoteJob*));remoteResponses=xQueueCreate(1,sizeof(RemoteJob*));
 remoteWorkerReady=remoteJobs&&remoteResponses&&xTaskCreate(remoteWorker,"doll-uplink",10240,nullptr,1,nullptr)==pdPASS;
 if(!remoteWorkerReady){remoteError="worker_unavailable";remoteEnabled=false;}
 configTime(0,0,"pool.ntp.org","time.cloudflare.com");
}
static void remoteSnapshotTool(JsonObject snapshot,const char *field,const char *name){
 JsonDocument request;request["jsonrpc"]="2.0";request["id"]=1;request["method"]="tools/call";
 request["params"]["name"]=name;request["params"]["arguments"].to<JsonObject>();
 JsonDocument response=rpc(request),data;
 String wire=response["result"]["content"][0]["text"]|"{}";deserializeJson(data,wire);snapshot[field].set(data.as<JsonObject>());
}
static bool remoteCommandAllowed(const String &name){
 return name=="set_channel_config"||name=="set_body_map"||name=="simulate_channel_input"||name=="doll_simulate_press"||
  name=="set_input_enabled"||name=="set_output_enabled"||name=="set_vibration"||name=="set_operating_mode"||name=="doll_set_led"||
  name=="capture_pressure_calibration"||name=="get_pressure_calibration"||name=="apply_pressure_calibration"||name=="cancel_pressure_calibration"||
  name=="scan_input_devices"||name=="get_sensor_config"||name=="set_sensor_config";
}
static void remoteAccept(RemoteJob *job){
 remoteHTTPCode=job->code;
 JsonDocument response;
 if(!job->error.isEmpty()||job->code!=200||deserializeJson(response,job->response)||!response["accepted"].as<bool>()||
    response["boot_id"].as<String>()!=job->boot||response["storage_cursor"].as<uint64_t>()!=job->cursor||
    response["storage_epoch"].as<String>()!=job->epoch){
  remoteFailures++;remoteError=!job->error.isEmpty()?job->error:String("exchange_rejected_")+String(job->code);
  remoteNextAt=millis()+min<uint32_t>(60000,1000UL<<(min<uint32_t>(remoteFailures,6)-1));return;
 }
 String error;
 if(job->cursor){JsonDocument ack;ack["boot_id"]=job->boot;ack["storage_epoch"]=job->epoch;ack["storage_cursor"]=job->cursor;
  if(!acknowledgeStoredEvents(ack.as<JsonVariantConst>(),error)){remoteError="local_ack_failed";remoteNextAt=millis()+1000;return;}
 }
 JsonDocument clock;clock["boot_id"]=touchBoot;clock["unix_time_ms"]=response["unix_time_ms"];
 syncDeviceClock(clock.as<JsonVariantConst>(),error);
 remoteAfter=response["next_cursor"]|remoteAfter;
 for(JsonVariant ack:response["acknowledged_commands"].as<JsonArray>())if(ack.as<String>()==remoteLastCommand)remoteResult="";
 for(JsonObject command:response["commands"].as<JsonArray>()){
  String id=command["id"]|"",name=command["name"]|"";
  if(id.length()!=32||id==remoteLastCommand)continue;
  JsonDocument result;result["id"]=id;
  if(!remoteCommandAllowed(name)||otaActive||otaCommitted)result["error"]="command_unavailable";
  else if(!eventClockSynced||command["expires_at_ms"].as<uint64_t>()<=deviceWallTime())result["error"]="command_expired";
  else{JsonDocument req;req["jsonrpc"]="2.0";req["id"]=1;req["method"]="tools/call";req["params"]["name"]=name;req["params"]["arguments"].set(command["arguments"]);JsonDocument reply=rpc(req);result["rpc"].set(reply.as<JsonObject>());}
  remoteLastCommand=id;remoteResult=encode(result);
 }
 remoteFailures=0;remoteError="";remoteLastOK=millis();remoteNextAt=millis()+(!remoteResult.isEmpty()||eventDiskCount?100:2000);
}
static void remoteTick(){
 RemoteJob *finished=nullptr;
 if(remoteResponses&&xQueueReceive(remoteResponses,&finished,0)==pdTRUE){
  remotePending=false;if(finished->generation==remoteGeneration&&remoteEnabled)remoteAccept(finished);delete finished;
 }
 if(!remoteEnabled||remotePending||!remoteJobs||WiFi.status()!=WL_CONNECTED||configAP||otaActive||otaCommitted)return;
 if(remoteFailures==0&&touchSeq!=remoteObservedSeq)remoteNextAt=0;
 if((int32_t)(millis()-remoteNextAt)<0)return;
 timeval now;gettimeofday(&now,nullptr);
 if(remoteURL.startsWith("https://")&&now.tv_sec<1704067200){remoteError="waiting_for_network_time";remoteNextAt=millis()+2000;return;}
 if(ESP.getFreeHeap()<45000){remoteError="waiting_for_free_heap";remoteNextAt=millis()+2000;return;}
 JsonDocument data;data["protocol"]=1;touchRead(data["batch"].to<JsonObject>(),remoteAfter,touchBoot,true);
 JsonObject snapshot=data["snapshot"].to<JsonObject>();status(snapshot["status"].to<JsonObject>());
 remoteSnapshotTool(snapshot,"channels","get_channel_config");remoteSnapshotTool(snapshot,"capabilities","get_channel_capabilities");
 remoteSnapshotTool(snapshot,"values","read_channel_values");remoteSnapshotTool(snapshot,"operating_mode","get_operating_mode");
 remoteSnapshotTool(snapshot,"calibration","get_pressure_calibration");remoteSnapshotTool(snapshot,"sensors","get_sensor_config");
 if(!remoteResult.isEmpty()){JsonDocument r;deserializeJson(r,remoteResult);data["command_results"].to<JsonArray>().add(r.as<JsonObject>());}
 RemoteJob *job=new RemoteJob();job->body=encode(data);
 job->url=remoteURL+"/api/device/exchange";job->token=remoteToken;job->ca=remoteCA;job->generation=remoteGeneration;
 job->boot=touchBoot;job->epoch=eventStorageEpoch;job->cursor=data["batch"]["storage_cursor"]|0ULL;
 if(job->body.length()>65536){remoteError="snapshot_too_large";delete job;remoteNextAt=millis()+5000;return;}
 if(xQueueSend(remoteJobs,&job,0)==pdTRUE){remotePending=true;remoteObservedSeq=touchSeq;}else delete job;
}
