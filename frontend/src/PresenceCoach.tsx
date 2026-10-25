import {useEffect,useRef,useState} from "react";
import {Camera,CameraOff,Mic,MicOff,ShieldCheck,Activity,AudioLines,AlertTriangle,CheckCircle2} from "lucide-react";
import {FilesetResolver,PoseLandmarker,ObjectDetector} from "@mediapipe/tasks-vision";

type GrammarIssue={label:string,fix:string};
const grammarRules:[RegExp,string,string][]=[
 [/\bi am agree\b/gi,"“I am agree” is not grammatical.","Say “I agree.”"],
 [/\bhe don't\b/gi,"Subject–verb agreement.","Say “he doesn't.”"],
 [/\bshe don't\b/gi,"Subject–verb agreement.","Say “she doesn't.”"],
 [/\bi didn't went\b/gi,"Use the base verb after “didn't”.","Say “I didn't go.”"],
 [/\bmore better\b/gi,"Avoid the double comparative.","Say “better.”"],
 [/\bdiscuss about\b/gi,"“Discuss” doesn't need “about” here.","Say “discuss the topic.”"],
 [/\baccording to me\b/gi,"This can sound unnatural in formal interview answers.","Try “In my opinion…”"],
 [/\bhe have\b/gi,"Subject–verb agreement.","Say “he has.”"],
 [/\bshe have\b/gi,"Subject–verb agreement.","Say “she has.”"],
 [/\bi has\b/gi,"Subject–verb agreement.","Say “I have.”"],
 [/\bthey was\b/gi,"Subject–verb agreement.","Say “they were.”"],
 [/\byour welcome\b/gi,"Common word-choice mix-up.","Say “you're welcome.”"]
];
function checkGrammar(text:string):GrammarIssue[]{return grammarRules.filter(([r])=>{r.lastIndex=0;return r.test(text)}).map(([,label,fix])=>({label,fix}));}
export default function PresenceCoach(){
 const video=useRef<HTMLVideoElement>(null),overlay=useRef<HTMLCanvasElement>(null),stream=useRef<MediaStream|null>(null),pose=useRef<PoseLandmarker|null>(null),objectDetector=useRef<ObjectDetector|null>(null),raf=useRef<number>(0),last=useRef(0),lastPhoneAlert=useRef(0),recognition=useRef<any>(null),finalTranscript=useRef(""),interimTranscript=useRef("");
 const [phoneModelStatus,setPhoneModelStatus]=useState("Not loaded"),[poseModelStatus,setPoseModelStatus]=useState("Not loaded"),[grammarBusy,setGrammarBusy]=useState(false),[grammarSource,setGrammarSource]=useState("Built-in checks"),[camera,setCamera]=useState(false),[camError,setCamError]=useState(""),[posture,setPosture]=useState("Start the camera to assess posture."),[poseReady,setPoseReady]=useState(false),[phoneDetected,setPhoneDetected]=useState(false),[phoneAlert,setPhoneAlert]=useState("No phone detected in the camera frame."),[mic,setMic]=useState(false),[transcript,setTranscript]=useState(""),[speechError,setSpeechError]=useState(""),[issues,setIssues]=useState<GrammarIssue[]>([]),[pace,setPace]=useState("Not measured"),[started,setStarted]=useState(0),[speechLanguage,setSpeechLanguage]=useState("en-IN");
 useEffect(()=>()=>{cancelAnimationFrame(raf.current);stream.current?.getTracks().forEach(t=>t.stop());pose.current?.close();objectDetector.current?.close()},[]);
 async function startCamera(){
  setCamError("");
  try{
   const s=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});stream.current=s;setCamera(true);
   await new Promise(resolve=>setTimeout(resolve,80));
   if(video.current){video.current.srcObject=s;await video.current.play();}
   try{
    const vision=await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm");
    try {
     pose.current=await PoseLandmarker.createFromOptions(vision,{baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",delegate:"CPU"},runningMode:"VIDEO",numPoses:1});
     setPoseModelStatus("Loaded");
    } catch (err) { setPoseModelStatus("Failed to load"); throw err; }
    try{
     objectDetector.current=await ObjectDetector.createFromOptions(vision,{baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite",delegate:"CPU"},runningMode:"VIDEO",scoreThreshold:.25,maxResults:20});
     setPhoneModelStatus("Loaded — scanning live frames");setPhoneAlert("Phone detector loaded. Scanning the camera feed.");
    }catch(err){setPhoneModelStatus("Failed to load");setPhoneAlert("Phone model failed to load. Check the browser Console and internet access.");}
    setPoseReady(true);detect();
   }catch(err){setPoseModelStatus("Failed to load");setPosture("Camera is on, but pose analysis could not load. Check internet access and browser Console.");setCamError("Pose model failed to load. Check internet access, then stop and restart the camera.");}
  }catch{setCamError("Camera permission was blocked or no camera was found. Allow camera access in your browser and try again.");}
 }
 function detect(){
  const v=video.current,p=pose.current;if(!v||!p)return;
  const loop=(now:number)=>{
   if(!video.current||!pose.current){return;}
   const videoEl=video.current,poseModel=pose.current,canvas=overlay.current,ctx=canvas?.getContext("2d");
   if(now-last.current>180&&videoEl.readyState>=2&&videoEl.videoWidth>0){
    last.current=now;
    try{
     const res=poseModel.detectForVideo(videoEl,now);const lm=res.landmarks?.[0];
     if(canvas&&ctx){
      if(canvas.width!==videoEl.videoWidth)canvas.width=videoEl.videoWidth;
      if(canvas.height!==videoEl.videoHeight)canvas.height=videoEl.videoHeight;
      ctx.clearRect(0,0,canvas.width,canvas.height);
      if(lm){
       const links:[number,number][]=[[11,12],[11,23],[12,24],[23,24],[11,13],[13,15],[12,14],[14,16],[23,25],[25,27],[24,26],[26,28],[0,11],[0,12]];
       ctx.lineWidth=Math.max(2,canvas.width/320);ctx.strokeStyle="#ffffff";ctx.fillStyle="#ffffff";
       links.forEach(([a,b])=>{const A=lm[a],B=lm[b];if(A&&B&&(A.visibility??1)>.35&&(B.visibility??1)>.35){ctx.beginPath();ctx.moveTo(A.x*canvas.width,A.y*canvas.height);ctx.lineTo(B.x*canvas.width,B.y*canvas.height);ctx.stroke();}});
       lm.forEach((pt:any)=>{if((pt.visibility??1)>.4){ctx.beginPath();ctx.arc(pt.x*canvas.width,pt.y*canvas.height,Math.max(2,canvas.width/180),0,Math.PI*2);ctx.fill();}});
      }
     }
     const ls=lm?.[11],rs=lm?.[12],lh=lm?.[23],rh=lm?.[24];
     if(ls&&rs&&(ls.visibility??0)>.55&&(rs.visibility??0)>.55){
      const shoulderDx=Math.abs(ls.x-rs.x);
      const shoulderTilt=shoulderDx>0.01?Math.abs(ls.y-rs.y)/shoulderDx:1;
      const shoulderMid=(ls.x+rs.x)/2;
      const hipsVisible=!!(lh&&rh&&(lh.visibility??0)>.5&&(rh.visibility??0)>.5);
      const hipMid=hipsVisible?((lh!.x+rh!.x)/2):shoulderMid;
      const torsoShift=Math.abs(shoulderMid-hipMid);
      const shouldersLow=(ls.y+rs.y)/2>.82;
      const shouldersHigh=(ls.y+rs.y)/2<.16;
      if(shouldersLow||shouldersHigh) setPosture("FRAMING: adjust the camera so your shoulders and upper torso are comfortably in view.");
      else if(shoulderTilt>.22) setPosture("POSTURE: your shoulders appear uneven. Try sitting comfortably level.");
      else if(hipsVisible&&torsoShift>.13) setPosture("POSTURE: your upper body appears shifted sideways. Re-centre if comfortable.");
      else if(shoulderTilt<.10&&(!hipsVisible||torsoShift<.07)) setPosture("GOOD: your shoulders look level and your upper body appears centred. Keep a relaxed, natural posture.");
      else setPosture("OK: posture looks reasonably balanced. Keep your shoulders relaxed and face the camera naturally.");
     }else setPosture("TRACKING: move into view so both shoulders are clearly visible.");
     const detector=objectDetector.current;
     if(detector){
      const detections=detector.detectForVideo(videoEl,now).detections as any[];
      const phone=detections.find(d=>d.categories?.some((c:any)=>/cell phone|mobile phone|phone/i.test(c.categoryName||"")&&c.score>=.25));
      setPhoneDetected(!!phone);
      if(phone){const phoneCategory=phone.categories?.find((c:any)=>/cell phone|mobile phone|phone/i.test(c.categoryName||""));setPhoneAlert(`PHONE DETECTED (${Math.round((phoneCategory?.score||0)*100)}% model confidence). Put it aside before continuing.`);
       const b=phone.boundingBox;if(canvas&&ctx&&b){ctx.lineWidth=Math.max(3,canvas.width/180);ctx.strokeStyle="#ffffff";ctx.fillStyle="rgba(0,0,0,.78)";ctx.strokeRect(b.originX,b.originY,b.width,b.height);ctx.fillRect(b.originX,b.originY-28,Math.min(b.width+120,canvas.width-b.originX),28);ctx.fillStyle="#ffffff";ctx.font=`bold ${Math.max(14,canvas.width/45)}px sans-serif`;ctx.fillText("PHONE DETECTED",b.originX+5,Math.max(18,b.originY-8));}
       if(now-lastPhoneAlert.current>9000){lastPhoneAlert.current=now;if("speechSynthesis" in window){window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance("Phone detected in camera frame."));}}
      }else setPhoneAlert("No phone detected right now. Detection can miss obscured or partly visible devices.");
     }else{setPhoneDetected(false);setPhoneAlert(`Phone detector is not running (${phoneModelStatus}). Check model loading and internet access.`);}
    }catch(e){
      const message=e instanceof Error?e.message:String(e);
      if(message.toLowerCase().includes("object")||message.toLowerCase().includes("tensor")||message.toLowerCase().includes("image")){
       setPhoneModelStatus("Inference error");setPhoneAlert("Phone model loaded but could not analyse a camera frame. Stop and restart the camera; check Console if it continues.");
      }
    }
   }
   raf.current=requestAnimationFrame(loop);
  };
  raf.current=requestAnimationFrame(loop);
 }
 function stopCamera(){cancelAnimationFrame(raf.current);stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;pose.current?.close();pose.current=null;objectDetector.current?.close();objectDetector.current=null;setCamera(false);setPoseReady(false);setPoseModelStatus("Not loaded");setPhoneModelStatus("Not loaded");setPhoneDetected(false);setPhoneAlert("Camera stopped. Start the camera to scan again.");if(overlay.current){const c=overlay.current.getContext("2d");c?.clearRect(0,0,overlay.current.width,overlay.current.height);}setPosture("Camera stopped.");}
 function startMic(){
  const w=window as any;const SR=w.SpeechRecognition||w.webkitSpeechRecognition;
  if(!SR){setSpeechError("Speech recognition is not supported in this browser. Try the latest Google Chrome or Microsoft Edge.");return;}
  try{
   // Keep the final transcript separately; only append newly-finalised results.
   // Browser recognition returns the full results list on each event, so appending
   // every result on every event caused repeated words and sentences.
   finalTranscript.current=transcript.trim();interimTranscript.current="";
   const r=new SR();recognition.current=r;r.continuous=true;r.interimResults=true;r.maxAlternatives=1;r.lang=speechLanguage;
   r.onresult=(e:any)=>{
    let changedFinals="";let interim="";
    for(let i=e.resultIndex;i<e.results.length;i++){
     const result=e.results[i];const text=String(result?.[0]?.transcript||"").trim();
     if(!text)continue;
     if(result.isFinal)changedFinals+=text+" ";else interim+=text+" ";
    }
    if(changedFinals.trim())finalTranscript.current=(finalTranscript.current+" "+changedFinals.trim()).trim();
    interimTranscript.current=interim.trim();
    setTranscript([finalTranscript.current,interimTranscript.current].filter(Boolean).join(" "));
   };
   r.onerror=(e:any)=>{const messages:any={"not-allowed":"Microphone access is blocked. Allow microphone access in your browser settings.","no-speech":"No speech was detected. Speak clearly and try again.","audio-capture":"No microphone was found. Check your microphone connection."};setSpeechError(messages[e?.error]||"Speech recognition stopped. Check microphone permission and try again.");};
   r.onend=()=>{setMic(false);recognition.current=null;};
   r.start();setMic(true);setSpeechError("");setStarted(Date.now());
  }catch{setSpeechError("Could not start speech recognition. Check microphone permission and make sure no other recognition session is running.");setMic(false);}
 }
 async function runGrammarCheck(source=transcript){
  const clean=source.trim();if(!clean){setIssues([]);setGrammarSource("No text to check");return;}
  setGrammarBusy(true);setGrammarSource("Checking…");
  try{
   const language=speechLanguage==="hi-IN"?"hi":speechLanguage==="en-IN"?"en-US":"en-US";
   const body=new URLSearchParams({text:clean,language});
   const response=await fetch("https://api.languagetool.org/v2/check",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
   if(!response.ok)throw new Error("Grammar service unavailable");
   const data=await response.json();
   const remote:GrammarIssue[]=(data.matches||[]).slice(0,30).map((m:any)=>({label:`${m.message}${m.context?.text?` — “${m.context.text.slice(Math.max(0,m.context.offset-18),Math.min(m.context.text.length,m.context.offset+m.context.length+24))}”`:""}`,fix:m.replacements?.length?`Suggestion: ${m.replacements.slice(0,3).map((r:any)=>r.value).join(" / ")}`:"Review this phrase and its context."}));
   const local=checkGrammar(clean);const seen=new Set(remote.map(x=>x.label.toLowerCase()));setIssues([...remote,...local.filter(x=>!seen.has(x.label.toLowerCase()))]);setGrammarSource("LanguageTool + common-pattern checks");
  }catch{
   setIssues(checkGrammar(clean));setGrammarSource("Offline fallback checks (limited)");setSpeechError("Online grammar service was unavailable, so only common-pattern checks were used.");
  }finally{setGrammarBusy(false);}
 }
 function stopMic(){try{recognition.current?.stop?.();}catch{}recognition.current=null;setMic(false);const finalText=finalTranscript.current.trim();setTranscript(finalText);const mins=Math.max((Date.now()-started)/60000,.1);const words=finalText.split(/\s+/).filter(Boolean).length;setPace(`${Math.round(words/mins)} words/min (rough estimate)`);void runGrammarCheck(finalText);}
 const words=transcript.trim().split(/\s+/).filter(Boolean).length;
 return <><div className="heading"><div><div className="eyebrow">CAMERA + SPEECH PRACTICE</div><h1>Presence & Speaking Coach</h1><p>Practice your delivery with local camera cues and a speech transcript. This is coaching, not a hiring or dishonesty detector.</p></div></div>
 <div className="presence-grid">
  <section className="card"><div className="card-head"><div><h3><Camera size={17}/> Camera posture coach</h3><p>Video is processed in your browser; it is not uploaded by this feature.</p></div><span className={camera?"completed":"pending"}>{camera?"Camera on":"Camera off"}</span></div>
   <div className="camera-stage">{camera?<><video ref={video} autoPlay muted playsInline/><canvas ref={overlay} className="camera-overlay"/><div className="camera-hud"><span>LIVE ANALYSIS</span><span>{phoneDetected?"PHONE ALERT":"POSE TRACKING"}</span></div></>:<div className="camera-placeholder"><CameraOff size={38}/><b>Camera preview</b><small>Allow access to begin posture cues.</small></div>}</div>
   {camError&&<p className="presence-error">{camError}</p>}
   <div className="presence-feedback"><Activity size={18}/><div><b>Live posture analysis</b><p>{posture}</p><small>Updates continuously while the camera is active.</small></div></div>
   <div className={`phone-detection ${phoneDetected?"phone-detected":"phone-clear"}`} role="status"><div className="phone-indicator">{phoneDetected?<AlertTriangle size={19}/>:<ShieldCheck size={19}/>}</div><div><b>{phoneDetected?"Phone detected":"Phone detection"}</b><p>{phoneAlert}</p><small>Visual detection can miss small, hidden, or partially visible phones.</small></div></div>
   <p className="tiny-note">Pose model: {poseModelStatus}. Phone model: {phoneModelStatus}. Phone detection uses an object-recognition model and can miss small, obscured, or out-of-frame devices.</p>
   <div className="actions">{!camera?<button className="btn primary" onClick={startCamera}><Camera size={15}/> Start camera</button>:<button className="btn secondary" onClick={stopCamera}><CameraOff size={15}/> Stop camera</button>}</div>
   <div className="framing-list"><b>Quick framing checklist</b><span><CheckCircle2 size={14}/> Keep your face and shoulders visible</span><span><CheckCircle2 size={14}/> Place the camera near eye level</span><span><CheckCircle2 size={14}/> Use comfortable, natural posture</span></div>
  </section>
  <section className="card"><div className="card-head"><div><h3><AudioLines size={17}/> Speech & grammar coach</h3><p>Speech-to-text uses your browser's recognition service; choose the spoken language below.</p></div><span className={mic?"completed":"pending"}>{mic?"Listening":"Ready"}</span></div>
   <label className="field-label" htmlFor="speech-language">Recognition language</label><select id="speech-language" className="select speech-language" value={speechLanguage} disabled={mic} onChange={e=>setSpeechLanguage(e.target.value)}><option value="en-IN">English (India)</option><option value="en-US">English (US)</option><option value="hi-IN">Hindi (हिन्दी)</option></select>
   <p className="tiny-note">Choose one language before starting. Mixed Hindi-English speech may be transcribed inconsistently; switch languages and record a separate attempt for best results.</p>
   <div className="speech-controls"><button className="btn primary" onClick={mic?stopMic:startMic}>{mic?<><MicOff size={15}/> Stop & analyse</>:<><Mic size={15}/> Start speaking</>}</button><button className="btn secondary" onClick={()=>{try{recognition.current?.abort?.();}catch{}recognition.current=null;finalTranscript.current="";interimTranscript.current="";setTranscript("");setMic(false);setIssues([]);setPace("Not measured");setSpeechError("");}}>Clear</button></div>
   {speechError&&<p className="presence-error">{speechError}</p>}
   <label className="field-label">Recognized transcript</label><textarea className="textarea speech-transcript" value={transcript} onChange={e=>setTranscript(e.target.value)} placeholder="Your recognized speech appears here. You can also paste a transcript to review grammar."/>
   <div className="speech-stats"><div><small>Words</small><b>{words}</b></div><div><small>Speaking pace</small><b>{pace}</b></div><div><small>Grammar flags</small><b>{issues.length}</b></div></div>
   <button className="btn secondary" onClick={()=>void runGrammarCheck(transcript)} disabled={grammarBusy}>{grammarBusy?"Checking grammar…":"Check grammar"}</button>
   <div className="grammar-results"><b>Grammar suggestions</b><small className="grammar-source">{grammarSource}</small>{issues.length?issues.map((x,i)=><div className="grammar-item" key={i}><AlertTriangle size={15}/><div><p>{x.label}</p><small>{x.fix}</small></div></div>):<p className="sub">{transcript.trim()?"No matches in the small built-in rule set. This does not guarantee the transcript is grammatically correct.":"Start speaking or paste a transcript, then check grammar."}</p>}</div>
   <p className="tiny-note">Recognition quality depends on your browser, microphone, accent, and background noise. Browser speech recognition may process audio online. Grammar checks are rule-based and limited; review suggestions rather than treating them as definitive.</p>
  </section>
 </div></>;
}
