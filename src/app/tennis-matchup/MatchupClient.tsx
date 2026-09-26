"use client";
import { useEffect, useRef } from "react";
import { matchupShell } from "./shell";

export default function MatchupClient({indexUrl}:{indexUrl:string}) {
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const node=host.current;
    if(!node)return;
    const controller=new AbortController();
    // Reset the isolated DOM island on a React development remount.
    node.innerHTML=matchupShell;
    import("./runtime/panel.mjs").then(({mountMatchup})=>{
      if(!controller.signal.aborted)return mountMatchup(node,indexUrl,controller.signal);
    }).catch(()=>{
      if(!controller.signal.aborted){
        const message=node.querySelector('[role="status"]');
        if(message)message.textContent="The comparison could not load. Please reload to try again.";
      }
    });
    return ()=>controller.abort();
  },[indexUrl]);
  return <div ref={host} dangerouslySetInnerHTML={{__html:matchupShell}} />;
}
