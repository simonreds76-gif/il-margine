"use client";
import Link from "next/link";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import styles from "./board.module.css";
import type { Circuit } from "./types";
import { boardUrl } from "./board-url";

export function TourSwitch({circuit,historyDay,archive}:{circuit:Circuit;historyDay?:string;archive:boolean}) {
  const query=useSearchParams();
  const record=query.get("record");
  return <nav className={styles.circuit} aria-label="Tennis tour">
    {(["ATP","WTA"] as const).map(tour=>{
      const showRecord=!archive && (record==="30d" || record==="sent30");
      const href=archive && tour==="ATP" ? "/drop-shot-desk?tour=atp&view=archive"
        : boardUrl(tour, historyDay, showRecord ? record : null);
      return <Link key={tour} prefetch={false} aria-current={circuit===tour?"page":undefined}
        href={href+(showRecord?"#big-drop-returns":"")}>
        <span className={styles.tourBadge} data-tour={tour}><Image unoptimized width={58} height={24} src={tour==="ATP"?"/icons/drop-shot-desk/atp-tour.png":"/icons/drop-shot-desk/wta-tour.svg"} alt={tour}/></span>
        <small>{tour==="ATP"?"incl. Challenger":"incl. WTA 125"}</small>
      </Link>;
    })}
  </nav>;
}
