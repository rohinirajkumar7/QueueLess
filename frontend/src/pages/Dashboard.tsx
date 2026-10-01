
import {Link} from 'react-router-dom';
import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
import {useAuth} from '../store/auth';
import {Icon} from '../components/Icons';

export default function Dashboard(){
 const u=useAuth(s=>s.user);
 const orgs=useQuery({queryKey:['orgs'],queryFn:async()=>{const r=await api.get('/organizations');return r.data}});
 return <div className="page-wrap py-10 sm:py-14">
  <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="text-sm font-bold uppercase tracking-[.16em] text-indigo-600">Customer portal</p><h1 className="mt-2 text-4xl font-black tracking-tight">Good to see you, {u?.name?.split(' ')[0]}.</h1><p className="mt-2 text-slate-500">Find a service and take your place without standing in line.</p></div><Link to="/organizations" className="btn btn-accent"><Icon name="search" size={17}/> Find a service</Link></div>
  <div className="mt-9 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
   <div className="card overflow-hidden p-7"><div className="flex items-center justify-between"><div><p className="text-sm font-bold text-slate-500">Your next action</p><h2 className="mt-1 text-2xl font-black">Join a queue</h2></div><span className="grid h-11 w-11 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Icon name="queue"/></span></div><p className="mt-3 max-w-lg leading-6 text-slate-500">Browse active organizations, compare services and join the queue that fits your needs.</p><Link to="/organizations" className="btn btn-primary mt-6">Browse services <Icon name="arrow" size={16}/></Link></div>
   <div className="card p-7"><div className="flex items-center justify-between"><div><p className="text-sm font-bold text-slate-500">Organizations available</p><p className="mt-2 text-4xl font-black stat-number">{orgs.data?.length??'—'}</p></div><span className="grid h-11 w-11 place-items-center rounded-xl bg-sky-50 text-sky-600"><Icon name="building"/></span></div><p className="mt-3 text-sm text-slate-500">Active service providers on QueueLess.</p></div>
  </div>
  <div className="mt-8 grid gap-5 md:grid-cols-3">
   <Link to="/appointments" className="card p-6 transition hover:-translate-y-0.5 hover:shadow-xl"><span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-50 text-amber-600"><Icon name="calendar"/></span><h3 className="mt-5 font-extrabold">Appointments</h3><p className="mt-1 text-sm leading-6 text-slate-500">Book, view and cancel scheduled appointments.</p></Link>
   <Link to="/notifications" className="card p-6 transition hover:-translate-y-0.5 hover:shadow-xl"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><Icon name="bell"/></span><h3 className="mt-5 font-extrabold">Notifications</h3><p className="mt-1 text-sm leading-6 text-slate-500">Keep up with queue and appointment updates.</p></Link>
   <div className="card bg-slate-950 p-6 text-white"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 text-indigo-300"><Icon name="shield"/></span><h3 className="mt-5 font-extrabold">Your role</h3><p className="mt-1 text-sm leading-6 text-slate-400">Customer access is limited to your own queues, appointments and notifications.</p></div>
  </div>
 </div>
}
