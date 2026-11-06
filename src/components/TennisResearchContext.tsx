import {renderTennisContext} from '@/lib/tennis-context-html.mjs';
import context from '@/data/tennis-matchup-context-preview.json';
import './TennisResearchContext.css';
export default function TennisResearchContext({players}:{players:string[]}) {
 return <div dangerouslySetInnerHTML={{__html:renderTennisContext(players,context,{history:false})}}/>;
}
