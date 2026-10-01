
import type {ReactNode} from 'react';
import {useAuth} from './store/auth';
import {BrowserRouter,Routes,Route,Navigate} from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import Organizations from './pages/Organizations';
import OrgDetails from './pages/OrgDetails';
import QueuePage from './pages/QueuePage';
import Dashboard from './pages/Dashboard';
import Appointments from './pages/Appointments';
import Staff from './pages/Staff';
import Admin from './pages/Admin';
import Notifications from './pages/Notifications';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';

function Protected({children}:{children:ReactNode}){return localStorage.getItem('access_token')?<>{children}</>:<Navigate to="/login" replace/>}
function Role({role,children}:{role:'CUSTOMER'|'STAFF'|'ORG_ADMIN';children:ReactNode}){
 const user=useAuth(s=>s.user);
 const token=localStorage.getItem('access_token');
 if(!token)return <Navigate to="/login" replace/>;
 if(!user)return <div className="page-wrap py-16"><div className="card p-8 text-center text-slate-500">Loading your portal...</div></div>;
 if(user.role!==role)return <Navigate to={user.role==='CUSTOMER'?'/dashboard':user.role==='STAFF'?'/staff':'/admin'} replace/>;
 return <>{children}</>;
}

export default function App(){return <BrowserRouter><Routes><Route element={<Layout/>}>
 <Route path="/" element={<Home/>}/>
 <Route path="/login" element={<Login/>}/><Route path="/login/:type" element={<Login/>}/><Route path="/forgot-password" element={<ForgotPassword/>}/><Route path="/reset-password" element={<ResetPassword/>}/>
 <Route path="/register" element={<Register/>}/><Route path="/register/:type" element={<Register/>}/>
 <Route path="/organizations" element={<Protected><Organizations/></Protected>}/>
 <Route path="/organizations/:id" element={<Protected><OrgDetails/></Protected>}/>
 <Route path="/queue/:id" element={<Role role="CUSTOMER"><QueuePage/></Role>}/>
 <Route path="/dashboard" element={<Role role="CUSTOMER"><Dashboard/></Role>}/>
 <Route path="/appointments" element={<Role role="CUSTOMER"><Appointments/></Role>}/>
 <Route path="/notifications" element={<Role role="CUSTOMER"><Notifications/></Role>}/>
 <Route path="/staff" element={<Role role="STAFF"><Staff/></Role>}/>
 <Route path="/admin" element={<Role role="ORG_ADMIN"><Admin/></Role>}/>
 <Route path="*" element={<Navigate to="/"/>}/>
 </Route></Routes></BrowserRouter>}
