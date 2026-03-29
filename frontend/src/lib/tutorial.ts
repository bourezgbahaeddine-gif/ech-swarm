import { useCallback, useMemo, useState } from 'react';

const STORAGE_KEY = 'ech_tutorial_state_v2';
const VERSION = 'v2';

export type TutorialRole = 'journalist' | 'editor_chief';
export type TutorialPace = 'full' | 'quick';
export type TutorialStep =
    | 'welcome'
    | 'today_open'
    | 'news_open'
    | 'editor_edit'
    | 'editor_tools'
    | 'editor_submit'
    | 'chief_today'
    | 'chief_editorial'
    | 'chief_decision'
    | 'done';

export type TutorialState = {
    version: string;
    role?: TutorialRole;
    step?: TutorialStep;
    done?: boolean;
    pace?: TutorialPace;
};

function readState(): TutorialState {
    if (typeof window === 'undefined') {
        return { version: VERSION, done: true };
    }
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (!raw) return { version: VERSION, done: false };
        const parsed = JSON.parse(raw) as TutorialState;
        if (!parsed || parsed.version !== VERSION) {
            return { version: VERSION, done: false };
        }
        return { pace: 'full', ...parsed };
    } catch {
        return { version: VERSION, done: false };
    }
}

function writeState(next: TutorialState) {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function useTutorialState() {
    const [state, setState] = useState<TutorialState>(() => readState());

    const update = useCallback((partial: Partial<TutorialState>) => {
        setState((prev) => {
            const next = { ...prev, ...partial, version: VERSION };
            writeState(next);
            return next;
        });
    }, []);

    const reset = useCallback(() => {
        const next = { version: VERSION, done: false } as TutorialState;
        writeState(next);
        setState(next);
    }, []);

    const complete = useCallback(() => {
        update({ step: 'done', done: true });
    }, [update]);

    const active = useMemo(() => !state.done, [state.done]);

    return { state, update, reset, complete, active };
}
