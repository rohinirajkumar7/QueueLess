import {useState} from 'react';
import type {FormEvent} from 'react';
import {Link,useNavigate,useParams} from 'react-router-dom';
import {api,apiError} from '../services/api';
import {Icon} from '../components/Icons';

const choices=[
  {key:'customer',icon:'user' as const,title:'Customer',tag:'Join queues',body:'Create a personal account to find services, take digital tokens and manage appointments.',action:'Create customer account',href:'/register/customer',tone:'bg-indigo-50 text-indigo-600'},
  {key:'organization',icon:'building' as const,title:'Organization admin',tag:'Run a service',body:'Create your organization, services and staff workspace, then manage queues and analytics.',action:'Create organization',href:'/register/organization',tone:'bg-violet-50 text-violet-600'},
  {key:'staff',icon:'users' as const,title:'Staff member',tag:'Use an existing account',body:'Staff accounts are created by an organization admin. If you already have credentials, sign in here.',action:'Staff sign in',href:'/login/staff',tone:'bg-sky-50 text-sky-600'}
];

export default function Register(){
 const {type}=useParams();
 if(!type) return <RegistrationChooser/>;
 const organization=type==='organization';
 const nav=useNavigate();
 const [form,setForm]=useState({name:'',email:'',password:'',organization_name:'',description:'',address:''});
 const [error,setError]=useState(''); const [loading,setLoading]=useState(false);
 function set(k:keyof typeof form,v:string){setForm(f=>({...f,[k]:v}))}
 async function submit(e:FormEvent){
   e.preventDefault();setError('');setLoading(true);
   try{
     if(organization) await api.post('/auth/register-organization',form);
     else await api.post('/auth/register',{name:form.name,email:form.email,password:form.password,role:'CUSTOMER'});
     nav(organization?'/login/organization':'/login/customer');
   }catch(e){setError(apiError(e,'Registration could not be completed. Please try again.'));}
   finally{setLoading(false)}
 }
 return <div className="page-wrap py-10 sm:py-16">
   <div className="mx-auto max-w-3xl">
     <Link to="/register" className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-slate-900">← Back to account types</Link>
     <div className="mt-8 text-center">
       <span className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl ${organization?'bg-violet-600':'bg-indigo-600'} text-white shadow-lg`}><Icon name={organization?'building':'user'} size={24}/></span>
       <p className="mt-5 text-sm font-extrabold uppercase tracking-[.16em] text-indigo-600">{organization?'Organization onboarding':'Customer account'}</p>
       <h1 className="mt-2 text-4xl font-black tracking-tight sm:text-5xl">{organization?'Create your organization':'Create your QueueLess account'}</h1>
       <p className="mx-auto mt-3 max-w-xl text-slate-500">{organization?'Set up your organization admin account, then add services and staff.':'Join queues remotely, track your place in line and manage appointments from one account.'}</p>
     </div>
     <div className="card mt-8 p-6 sm:p-9">
       {error&&<div role="alert" className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-700">{error}</div>}
       <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
         {organization&&<>
           <div className="sm:col-span-2"><label className="label">Organization name</label><input className="input" value={form.organization_name} onChange={e=>set('organization_name',e.target.value)} required placeholder="e.g. CityCare Clinic"/></div>
           <div><label className="label">Address</label><input className="input" value={form.address} onChange={e=>set('address',e.target.value)} placeholder="123 Main Street"/></div>
           <div><label className="label">Description</label><input className="input" value={form.description} onChange={e=>set('description',e.target.value)} placeholder="What does your organization offer?"/></div>
         </>}
         <div><label className="label">Your name</label><input className="input" value={form.name} onChange={e=>set('name',e.target.value)} required placeholder="Full name"/></div>
         <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={e=>set('email',e.target.value)} required placeholder="you@example.com"/></div>
         <div className="sm:col-span-2"><label className="label">Password</label><input className="input" type="password" minLength={8} value={form.password} onChange={e=>set('password',e.target.value)} required placeholder="At least 8 characters"/><p className="mt-2 text-xs text-slate-400">Use at least 8 characters. Keep your password private.</p></div>
         <div className="sm:col-span-2"><button disabled={loading} className={`btn w-full py-3.5 ${organization?'bg-violet-600 text-white shadow-lg shadow-violet-600/20 hover:bg-violet-700':'btn-primary'}`}>{loading?'Creating account...':organization?'Create organization':'Create customer account'} <Icon name="arrow" size={17}/></button></div>
       </form>
       <p className="mt-6 text-center text-sm text-slate-500">Already have an account? <Link className="font-extrabold text-indigo-600 hover:text-indigo-700" to={organization?'/login/organization':'/login/customer'}>Sign in</Link></p>
     </div>
   </div>
 </div>
}

function RegistrationChooser(){
 return <div className="page-wrap py-12 sm:py-20">
   <div className="mx-auto max-w-3xl text-center">
     <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-950 text-white shadow-lg"><Icon name="spark" size={24}/></span>
     <p className="mt-6 text-sm font-extrabold uppercase tracking-[.16em] text-indigo-600">Get started with QueueLess</p>
     <h1 className="mt-2 text-4xl font-black tracking-tight sm:text-5xl">Choose how you’ll use QueueLess.</h1>
     <p className="mx-auto mt-4 max-w-2xl text-slate-500">There are three role-based experiences. Customers and organizations can create accounts here; staff accounts are created by their organization admin.</p>
   </div>
   <div className="mx-auto mt-10 grid max-w-6xl gap-5 lg:grid-cols-3">
     {choices.map(c=><Link key={c.key} to={c.href} className="portal-card card group p-7 transition duration-200 hover:-translate-y-1 hover:border-indigo-200 hover:shadow-soft">
       <div className="relative z-10 flex items-start justify-between"><span className={`grid h-12 w-12 place-items-center rounded-2xl ${c.tone}`}><Icon name={c.icon} size={22}/></span><span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-slate-500">{c.tag}</span></div>
       <h2 className="relative z-10 mt-7 text-2xl font-black">{c.title}</h2>
       <p className="relative z-10 mt-3 min-h-[72px] text-sm leading-6 text-slate-500">{c.body}</p>
       <span className="relative z-10 mt-7 inline-flex items-center gap-2 font-extrabold text-indigo-600 group-hover:gap-3">{c.action}<Icon name="arrow" size={17}/></span>
     </Link>)}
   </div>
   <div className="mx-auto mt-8 max-w-6xl rounded-2xl border border-slate-200 bg-white px-5 py-4 text-center text-sm text-slate-500 shadow-sm">Already have credentials? <Link className="font-extrabold text-slate-900" to="/login">Choose a sign-in portal</Link>.</div>
 </div>
}
