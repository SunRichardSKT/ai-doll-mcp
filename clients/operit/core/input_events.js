// Input semantics shared by phone context and the existing reply queue.
function key(e){
 if((e.sensor_type||'pressure')==='pressure')return e.touch_id;
 const id=e.seq??e.event_id??e.archive_event_id;
 return id?e.sensor_type+':'+id:null;
}
function phase(e,policy){
 const kind=e.sensor_type||'pressure';
 if(kind==='pressure')return e.phase==='start';
 if(kind==='motion')return (!policy||policy.motion_enabled===true)&&['orientation','shake'].includes(e.phase);
 if(kind==='switch')return (!policy||policy.switch_enabled===true)&&e.phase==='close';
 if(kind==='temperature')return (!policy||policy.temperature_enabled===true)&&e.phase==='sample'&&Number.isFinite(e.value);
 return false;
}
exports.key=key;exports.phase=phase;
