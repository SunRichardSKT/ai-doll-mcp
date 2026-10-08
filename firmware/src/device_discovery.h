#pragma once
#include <WiFiUdp.h>
#include <mbedtls/md.h>

// Only paired clients can authenticate replies. Requests contain no credentials.
static constexpr uint16_t DISCOVERY_PORT=28768;
static const char* DISCOVERY_PROTOCOL="ai-doll-discovery-v1";
static WiFiUDP discoveryUDP;
static IPAddress discoveryBound;
static bool discoveryActive=false;
static uint32_t discoveryLastReply=0,discoveryLastBind=0;

static void __attribute__((noinline)) discoveryTick(){
 bool ready=mcpEnabled&&WiFi.status()==WL_CONNECTED;
 IPAddress current=WiFi.localIP();
 if(discoveryActive&&(!ready||current!=discoveryBound)){
  discoveryUDP.stop();discoveryActive=false;
 }
 if(!ready)return;
 if(!discoveryActive){
  if(millis()-discoveryLastBind<1000)return;
  discoveryLastBind=millis();
  discoveryActive=discoveryUDP.begin(DISCOVERY_PORT)!=0;discoveryBound=current;
  if(!discoveryActive)return;
 }
 int length=discoveryUDP.parsePacket();if(!length)return;
 IPAddress remote=discoveryUDP.remoteIP(),mask=WiFi.subnetMask();
 uint16_t remotePort=discoveryUDP.remotePort();
 bool sameSubnet=true;for(int i=0;i<4;i++)if((remote[i]&mask[i])!=(current[i]&mask[i]))sameSubnet=false;
 if(length>384||!sameSubnet||millis()-discoveryLastReply<50){discoveryUDP.flush();return;}
 char input[385];int count=discoveryUDP.read(input,384);discoveryUDP.flush();
 if(count!=length)return;
 input[count]=0;
 JsonDocument request;if(deserializeJson(request,input,count))return;
 String nonce=request["nonce"]|"";
 if(request["protocol"].as<String>()!=DISCOVERY_PROTOCOL||request["device_id"].as<String>()!=apName||nonce.length()!=32)return;
 for(size_t i=0;i<nonce.length();i++)if(!((nonce[i]>='0'&&nonce[i]<='9')||(nonce[i]>='a'&&nonce[i]<='f')))return;
 String canonical=String(DISCOVERY_PROTOCOL)+"\n"+nonce+"\n"+apName+"\n80\n"+VERSION;
 unsigned char digest[32];
 const mbedtls_md_info_t* info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!info||mbedtls_md_hmac(info,(const unsigned char*)token.c_str(),token.length(),
                         (const unsigned char*)canonical.c_str(),canonical.length(),digest)!=0)return;
 char proof[65];for(size_t i=0;i<32;i++)snprintf(proof+i*2,3,"%02x",digest[i]);
 JsonDocument response;response["protocol"]=DISCOVERY_PROTOCOL;response["nonce"]=nonce;
 response["device_id"]=apName;response["port"]=80;response["firmware"]=VERSION;response["proof"]=proof;
 String wire=encode(response);
 discoveryLastReply=millis();
 if(discoveryUDP.beginPacket(remote,remotePort)){
  discoveryUDP.write((const uint8_t*)wire.c_str(),wire.length());discoveryUDP.endPacket();
 }
}
