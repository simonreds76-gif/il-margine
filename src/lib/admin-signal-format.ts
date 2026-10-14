/** CSV parsing including quoted newlines and escaped double quotes. */
export function signalCsv(text:string):Record<string,string>[] {
 const records:string[][]=[];let row:string[]=[],cell="",quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(cell);cell="";}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(Boolean))records.push(row);row=[];cell="";}else cell+=c;}
 if(quoted)throw new Error("The saved CSV is incomplete.");
 row.push(cell);if(row.some(Boolean))records.push(row);
 const headers=(records.shift()??[]).map(h=>h.replace(/^\uFEFF/,''));
 if(new Set(headers).size!==headers.length)throw new Error('Duplicate CSV fields.');
 if(records.some(values=>values.length!==headers.length))throw new Error('The saved CSV has inconsistent columns.');
 return records.map(values=>Object.fromEntries(headers.map((h,i)=>[h,values[i]??''])));
}
export function resultGroup(row:Record<string,unknown>):string{
 const result=String(row.bet_outcome||row.result||row.settlement_status||row.status||'').trim().toLowerCase();
 if(['won','win','lost','loss','half_win','half_loss','half_won','half_lost','settled','push','void','cancelled','canceled'].includes(result))return 'settled';
 if(['pending','open','unsettled'].includes(result))return 'pending';
 return 'other';
}
