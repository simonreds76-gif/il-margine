import {conditionsFor,renderConditions} from '@/lib/tennis-conditions.mjs';
import './TennisConditions.css';

export default function TennisConditions({event,tour,date}:{event:string;tour:string;date:string}) {
  return <div dangerouslySetInnerHTML={{__html:renderConditions(conditionsFor({event,tour,date}),{compact:true})}} />;
}
