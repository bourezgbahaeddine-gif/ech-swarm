'use client';

import {
    createContext,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react';
import { useRouter, usePathname } from 'next/navigation';
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

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    isLoading: true,
    login: () => { },
    logout: () => { },
});

export const useAuth = () => useContext(AuthContext);

const PUBLIC_PATHS = ['/login'];

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        // Restore from localStorage
        const savedToken = localStorage.getItem('echorouk_token');
        const savedUser = localStorage.getItem('echorouk_user');

        if (savedToken && savedUser) {
            try {
                const parsedUser = JSON.parse(savedUser);
                setToken(savedToken);
                setUser(parsedUser);
                api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`;
            } catch {
                localStorage.removeItem('echorouk_token');
                localStorage.removeItem('echorouk_user');
            }
        }

        setIsLoading(false);
    }, []);

    useEffect(() => {
        // If on a public path, don't redirect
        if (PUBLIC_PATHS.includes(pathname)) return;

        // If loading, wait
        if (isLoading) return;

        // If not authenticated, redirect to login
        if (!user) {
            router.push('/login');
        }
    }, [isLoading, user, pathname, router]);

    const login = (newToken: string, newUser: AuthUser) => {
        localStorage.setItem('echorouk_token', newToken);
        localStorage.setItem('echorouk_user', JSON.stringify(newUser));
        api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;

        setToken(newToken);
        setUser(newUser);

        // Immediate redirect
        router.push('/');
    };

    const logout = async () => {
        try {
            await api.post('/auth/logout');
        } catch {
            // Ignore errors
        }

        localStorage.removeItem('echorouk_token');
        localStorage.removeItem('echorouk_user');
        delete api.defaults.headers.common['Authorization'];
        setUser(null);
        setToken(null);
        router.push('/login');
    };

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center mx-auto mb-3 animate-pulse">
                        <span className="text-white text-xl">⚡</span>
                    </div>
                    <p className="text-sm text-gray-500">جاري التحميل...</p>
                </div>
            </div>
        );
    }

    // Only render children if authenticated or on public path
    // But we need to render children for the layout to work? 
    // Actually, AppShell wraps children. AppShell might assume user exists.
    // If we are on public path, we render children (Login Page).
    // If we are authenticated, we render children (AppShell -> Dashboard).

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}
