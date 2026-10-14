import "server-only";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import catalog from "../../config/admin-monitor-catalog.json";
export {catalog};
type Manifest = {id:string;available:boolean;modified_at?:string;error?:string};
type SavedView = {generated_at:string;manifest:Manifest[];content?:string;source?:string;warning?:string};
const cloudCorners=new Set(['corners-v3-shadow-signals.csv','corners-v3-shadow-clv.csv','football-candidates','football-health']);
export async function readAdminSignalFile(id: string | null):Promise<SavedView> {
  if (!await isAdminSession()) throw new Error("Unauthorized");
  const view=catalog.find(v=>v.id===id);
  if (id && !view) throw new Error("Unknown model view");
  const read=async(key:string,selection:string)=>{
    try{return await getSupabaseAdmin().from("goalscorer_live_snapshot").select(selection).eq("snapshot_key",key).abortSignal(AbortSignal.timeout(10000)).single();}
    catch{return {data:null,error:true};}
  };
  const selection = id ? `generated_at:payload->>generated_at,manifest:payload->admin_manifest,content:payload->admin_files->>"${id}"` : "generated_at:payload->>generated_at,manifest:payload->admin_manifest";
  const [local,cloud]=await Promise.all([
    read("tennis_evidence_v1",selection),
    id&&view&&cloudCorners.has(id)?read("corners_state",`generated_at:payload->>generated_at,file:payload->files->"${view.file}"`):Promise.resolve(null)
  ]);
  const saved=local.data as unknown as SavedView|null;
  const hosted=cloud?.data as unknown as {generated_at:string;file?:{content?:string;mtime?:string}}|null;
  const localDate=saved?.manifest?.find(v=>v.id===id)?.modified_at;
  const localTime=Date.parse(localDate??'')||0,cloudTime=Date.parse(hosted?.file?.mtime??'')||0;
  if(hosted?.file&&typeof hosted.file.content==='string'&&cloudTime>localTime){
    return {generated_at:hosted.generated_at,manifest:[{id:id!,available:true,modified_at:hosted.file.mtime}],content:hosted.file.content,source:'Scheduled football snapshot'};
  }
  if(local.error||!saved)throw new Error("Private model snapshot unavailable.");
  return {...saved,source:'Daily private snapshot',...(cloud?.error?{warning:'The scheduled football snapshot could not be checked. Showing the dated saved copy.'}:{})};
}
