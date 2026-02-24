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
    login: (token: string, user: AuthUser) => void;
    logout: () => void;
}

type AuthState = {
    user: AuthUser | null;
    token: string | null;
    isLoading: boolean;
};

type AuthAction =
    | { type: 'hydrate'; payload: { token: string | null; user: AuthUser | null } }
    | { type: 'login'; payload: { token: string; user: AuthUser } }
    | { type: 'logout' };

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    isLoading: false,
    login: () => undefined,
    logout: () => undefined,
});

const PUBLIC_PATHS = ['/login'];

function getHomePathByRole(role: string): string {
    const normalized = (role || '').toLowerCase();
    if (normalized === 'director' || normalized === 'editor_chief') return '/';
    return '/news';
}

function readStoredAuth(): { token: string | null; user: AuthUser | null } {
    if (typeof window === 'undefined') {
        return { token: null, user: null };
    }

    const savedToken = window.localStorage.getItem('echorouk_token');
    const savedUser = window.localStorage.getItem('echorouk_user');

    if (!savedToken || !savedUser) {
        return { token: null, user: null };
    }

    try {
        const parsedUser = JSON.parse(savedUser) as AuthUser;
        api.defaults.headers.common.Authorization = `Bearer ${savedToken}`;
        return { token: savedToken, user: parsedUser };
    } catch {
        window.localStorage.removeItem('echorouk_token');
        window.localStorage.removeItem('echorouk_user');
        return { token: null, user: null };
    }
}

export const useAuth = () => useContext(AuthContext);

function authReducer(state: AuthState, action: AuthAction): AuthState {
    switch (action.type) {
        case 'hydrate':
            return {
                token: action.payload.token,
                user: action.payload.user,
                isLoading: false,
            };
        case 'login':
            return {
                token: action.payload.token,
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
        const initial = readStoredAuth();
        dispatch({ type: 'hydrate', payload: initial });
    }, []);

    useEffect(() => {
        if (isLoading) return;
        if (PUBLIC_PATHS.includes(pathname)) return;
        if (!user) router.push('/login');
    }, [isLoading, pathname, router, user]);

    const login = (newToken: string, newUser: AuthUser) => {
        window.localStorage.setItem('echorouk_token', newToken);
        window.localStorage.setItem('echorouk_user', JSON.stringify(newUser));
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        dispatch({ type: 'login', payload: { token: newToken, user: newUser } });
        router.push(getHomePathByRole(newUser.role));
    };

    const logout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // ignore network/logout errors
        }

        window.localStorage.removeItem('echorouk_token');
        window.localStorage.removeItem('echorouk_user');
        delete api.defaults.headers.common.Authorization;
        dispatch({ type: 'logout' });
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}
