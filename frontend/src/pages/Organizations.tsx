
import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
import {Link} from 'react-router-dom';
import {Icon} from '../components/Icons';

export default function Organizations(){
 // staleTime=45s matches backend Redis TTL so the browser doesn't re-fetch
 // on every navigation — a refetch only happens when the cache has expired.
 const q=useQuery({
   queryKey:['orgs'],
   queryFn:async()=>{const r=await api.get('/organizations');return r.data},
   staleTime: 45_000,
   gcTime: 120_000,
 });
 return <div className="page-wrap py-10 sm:py-14"><div className="max-w-2xl"><p className="text-sm font-bold uppercase tracking-[.16em] text-indigo-600">Customer directory</p><h1 className="mt-2 text-4xl font-black">Find a service</h1><p className="mt-2 text-slate-500">Choose an organization to see its services and current queue options.</p></div>{q.isLoading&&<div className="mt-8 card p-8 text-center text-slate-500">Loading organizations...</div>}{q.isError&&<div className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-700">Unable to load organizations.</div>}<div className="mt-8 grid gap-5 md:grid-cols-2">{q.data?.map((o:any)=><Link key={o.id} to={`/organizations/${o.id}`} className="card group p-6 transition hover:-translate-y-1 hover:border-indigo-200 hover:shadow-xl"><div className="flex items-start justify-between"><span className="grid h-12 w-12 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Icon name="building"/></span><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">Open</span></div><h2 className="mt-6 text-xl font-black">{o.name}</h2><p className="mt-2 min-h-12 text-sm leading-6 text-slate-500">{o.description||'Service organization on QueueLess.'}</p><div className="mt-5 flex items-center gap-2 text-sm text-slate-500"><Icon name="building" size={15}/>{o.address||'Address not provided'}</div><span className="mt-6 inline-flex items-center gap-2 text-sm font-extrabold text-indigo-600">View services <Icon name="arrow" size={16}/></span></Link>)}</div>{q.data?.length===0&&<div className="mt-8 card p-10 text-center"><h3 className="font-extrabold">No organizations yet</h3><p className="mt-2 text-sm text-slate-500">Check back when service providers are available.</p></div>}</div>
}
