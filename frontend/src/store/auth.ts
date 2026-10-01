import {create} from 'zustand';

export type Role = 'CUSTOMER' | 'STAFF' | 'ORG_ADMIN';

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  org_id?: number | null;
}

interface AuthState {
  user: User | null;
  setUser: (user: User | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({user}),
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({user: null});
  },
}));
