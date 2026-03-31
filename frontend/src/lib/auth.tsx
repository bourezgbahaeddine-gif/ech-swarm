'use client';

import {
    createContext,
    useContext,
    useEffect,
    useReducer,
    type ReactNode,
} from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export interface AuthUser {
    id: number;
    full_name_ar: string;
    username: string;
    role: string;
    departments: string[];
    specialization: string | null;
}

interface AuthContextType {
    user: AuthUser | null;
    token: string | null;
    isLoading: boolean;
    login: (user: AuthUser, token?: string | null) => void;
    logout: () => void;
}

type AuthState = {
    user: AuthUser | null;
    token: string | null;
    isLoading: boolean;
};

type AuthAction =
    | { type: 'hydrate'; payload: { user: AuthUser | null } }
    | { type: 'login'; payload: { user: AuthUser } }
    | { type: 'logout' };

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    isLoading: false,
    login: (_user?: AuthUser, _token?: string | null) => undefined,
    logout: () => undefined,
});

const PUBLIC_PATHS = ['/login'];

function getHomePathByRole(role: string): string {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'director' || normalized === 'editor_chief') return '/';
    return '/news';
}

export const useAuth = () => useContext(AuthContext);

function authReducer(state: AuthState, action: AuthAction): AuthState {
    switch (action.type) {
        case 'hydrate':
            return {
                token: null,
                user: action.payload.user,
                isLoading: false,
            };
        case 'login':
            return {
                token: null,
                user: action.payload.user,
                isLoading: false,
            };
        case 'logout':
            return {
                token: null,
                user: null,
                isLoading: false,
            };
        default:
            return state;
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();

    const [authState, dispatch] = useReducer(authReducer, {
        user: null,
        token: null,
        isLoading: true,
    });
    const { user, token, isLoading } = authState;

    useEffect(() => {
        let cancelled = false;

        const hydrate = async () => {
            try {
                const response = await api.get<AuthUser>('/auth/me');
                if (cancelled) return;
                dispatch({ type: 'hydrate', payload: { user: response.data } });
            } catch {
                if (cancelled) return;
                dispatch({ type: 'hydrate', payload: { user: null } });
            }
        };

        void hydrate();

        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (isLoading) return;
        if (PUBLIC_PATHS.includes(pathname)) return;
        if (!user) router.push('/login');
    }, [isLoading, pathname, router, user]);

    const login = (newUser: AuthUser, _token: string | null = null) => {
        dispatch({ type: 'login', payload: { user: newUser } });
        router.push(getHomePathByRole(newUser.role));
    };

    const logout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // ignore network/logout errors
        }

        dispatch({ type: 'logout' });
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

