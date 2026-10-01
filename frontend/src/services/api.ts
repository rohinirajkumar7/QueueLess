import axios from 'axios';

export const api=axios.create({
  baseURL:import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1',
  headers:{'Content-Type':'application/json'}
});

api.interceptors.request.use((config)=>{
  const token=localStorage.getItem('access_token');
  if(token) config.headers.Authorization=`Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response)=>response,
  (error)=>{
    if(error.response?.status===401){
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
    return Promise.reject(error);
  }
);

export function apiError(error:unknown,fallback='Something went wrong'){
  const e=error as {response?:{status?:number;data?:{detail?:unknown;error?:{message?:string}}};message?:string;code?:string};
  const detail=e.response?.data?.detail;
  if(typeof e.response?.data?.error?.message==='string') return e.response.data.error.message;
  if(typeof detail==='string') return detail;
  if(Array.isArray(detail)){
    const first=detail[0] as {msg?:string}|undefined;
    if(first?.msg) return first.msg;
  }
  if(e.code==='ERR_NETWORK') return 'Cannot reach the QueueLess API. Make sure Docker is running and the backend is healthy.';
  return fallback;
}
