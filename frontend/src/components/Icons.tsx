
import type { SVGProps } from 'react';

export type IconName = 'arrow'|'building'|'calendar'|'check'|'chevron'|'clock'|'close'|'dashboard'|'logOut'|'menu'|'queue'|'search'|'settings'|'shield'|'spark'|'users'|'bell'|'plus'|'refresh'|'play'|'skip'|'user';

const paths: Record<IconName, string> = {
  arrow:'M5 12h14m-6-6 6 6-6 6',
  building:'M3 21h18M6 21V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v17M14 21V9a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v12M9 7h2M9 11h2M9 15h2',
  calendar:'M7 3v4m10-4v4M4 9h16M5 5h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z',
  check:'m5 12 4 4L19 6',
  chevron:'m6 9 6 6 6-6',
  clock:'M12 7v5l3 2m7-2a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  close:'M6 6l12 12M18 6 6 18',
  dashboard:'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  logOut:'M10 17l5-5-5-5m5 5H3m12-7h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4',
  menu:'M4 6h16M4 12h16M4 18h16',
  queue:'M4 7h16M4 12h10M4 17h16',
  search:'m21 21-4.3-4.3m2.3-5.7a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  settings:'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm0-12v2m0 13v2m9-8h-2M5 12H3m15.36-6.36-1.42 1.42M7.06 16.94l-1.42 1.42m12.72 0-1.42-1.42M7.06 7.06 5.64 5.64',
  shield:'M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3Z',
  spark:'m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Zm7 12 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z',
  users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7-8a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87',
  bell:'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  plus:'M12 5v14M5 12h14',
  refresh:'M20 11a8.1 8.1 0 0 0-14.9-3M4 5v4h4M4 13a8.1 8.1 0 0 0 14.9 3M20 19v-4h-4',
  play:'m8 5 11 7-11 7V5Z',
  skip:'M5 4v16m3-10 11-6v12L8 10Z',
  user:'M20 21a8 8 0 0 0-16 0M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z'
};

export function Icon({name,size=18,className='',...props}:{name:IconName;size?:number;className?:string}&SVGProps<SVGSVGElement>){
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} {...props}><path d={paths[name]}/></svg>;
}
