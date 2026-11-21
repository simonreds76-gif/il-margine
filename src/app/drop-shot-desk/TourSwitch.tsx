"use client";
import Link from "next/link";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import styles from "./board.module.css";
import type { Circuit } from "./types";

export function TourSwitch({circuit,day,archive}:{circuit:Circuit;day:string;archive:boolean}) {
  const query=useSearchParams();
  const record=query.get("record");
  return <nav className={styles.circuit} aria-label="Tennis tour">
    {(["ATP","WTA"] as const).map(tour=>{
      const q=new URLSearchParams({tour:tour.toLowerCase(),day});
      if(archive && tour==="ATP")q.set("view","archive");
      if(!archive && (record==="30d" || record==="sent30"))q.set("record",record);
      return <Link key={tour} prefetch={false} aria-current={circuit===tour?"page":undefined}
        href={"/drop-shot-desk?"+q.toString()+(q.has("record")?"#big-drop-returns":"")}>
        <span className={styles.tourBadge} data-tour={tour}><Image unoptimized width={58} height={24} src={tour==="ATP"?"/icons/drop-shot-desk/atp-tour.png":"/icons/drop-shot-desk/wta-tour.svg"} alt={tour}/></span>
        <small>{tour==="ATP"?"incl. Challenger":"incl. WTA 125"}</small>
      </Link>;
    })}
  </nav>;
}
