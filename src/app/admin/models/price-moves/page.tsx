import Link from "next/link";
import {redirect} from "next/navigation";
import {isAdminSession} from "@/lib/admin-auth";
import MonitorRoundup from "./MonitorRoundup";
import {getRoundup} from "./reader";

export const dynamic="force-dynamic";
export const fetchCache="force-no-store";
export const metadata={title:"Tennis price moves · Private Monitor",robots:{index:false,follow:false}};
export default async function PrivatePriceMoves() {
  if(!await isAdminSession())redirect("/admin");
  const data=await getRoundup().catch(()=>undefined);
  return <main className="min-h-screen bg-[#0f1117] px-4 py-8 text-slate-100"><div className="mx-auto max-w-5xl">
    <Link className="text-sm text-emerald-200" href="/admin/models">← Model Monitor</Link>
    <h1 className="mt-4 text-3xl font-bold">Latest tennis price moves</h1>
    {data?<><p className="my-4 text-slate-300">Private Telegram roundup sent {new Date(data.sent).toLocaleString("en-GB",{timeZone:"UTC",dateStyle:"medium",timeStyle:"medium"})} UTC. All prices shown were recorded before the match.</p>
      <MonitorRoundup {...data}/></>:<p className="my-4 text-slate-300">{data===null?"No confirmed private roundup today or yesterday.":"The latest private roundup could not be verified."}</p>}
  </div></main>;
}
