
import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
import {Icon} from '../components/Icons';

export default function Notifications(){
 const q=useQuery({queryKey:['notifications'],queryFn:async()=>{const r=await api.get('/notifications');return r.data}});
 return <div className="page-wrap py-10 sm:py-14"><p className="text-sm font-bold uppercase tracking-[.16em] text-indigo-600">Customer portal</p><h1 className="mt-2 text-4xl font-black">Notifications</h1><p className="mt-2 text-slate-500">Updates about your queue and appointments.</p><div className="mt-8 max-w-3xl space-y-3">{q.data?.length?q.data.map((n:any)=>{const isRead=Boolean(n.read_at);return <div className="card flex gap-4 p-5" key={n.id}><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Icon name="bell" size={17}/></span><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-extrabold">{n.title}</h2>{isRead?<span className="text-xs font-bold text-slate-400">READ</span>:<span className="text-xs font-bold text-indigo-500">NEW</span>}</div><p className="mt-1 text-sm leading-6 text-slate-500">{n.message}</p></div></div>}):<div className="card p-10 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-slate-500"><Icon name="bell"/></span><h3 className="mt-4 font-extrabold">You're all caught up</h3><p className="mt-1 text-sm text-slate-500">New queue updates will appear here.</p></div>}</div></div>
}
