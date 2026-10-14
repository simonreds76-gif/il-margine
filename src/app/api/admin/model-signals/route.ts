import {NextResponse} from "next/server";
import {isAdminSession} from "@/lib/admin-auth";
import {readAdminSignalFile,catalog} from "@/lib/admin-signals-reader";
export const dynamic="force-dynamic";
export const fetchCache="force-no-store";
export async function GET(request:Request) {
 const json=(body:unknown,status=200)=>NextResponse.json(body,{status,headers:{"Cache-Control":"private, no-store"}});
 if(!await isAdminSession())return json({error:"Sign in to Admin."},401);
 const id=new URL(request.url).searchParams.get("view");
 if(id&&!catalog.some(v=>v.id===id))return json({error:"Unknown model view."},400);
 try {const data=await readAdminSignalFile(id);return json({ok:true,...data});}
 catch {return json({error:"Saved model data could not be loaded. Refresh to retry."},503);}
}
