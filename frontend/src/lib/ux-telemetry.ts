'use client';

import { useEffect, useRef } from 'react';

import { telemetryApi, type UxTelemetryEventPayload } from '@/lib/api';

type UxDetails = Record<string, unknown>;

function withPagePath(payload: UxTelemetryEventPayload): UxTelemetryEventPayload {
    if (payload.page_path || typeof window === 'undefined') {
        return payload;
    }
    return {
        ...payload,
        page_path: window.location.pathname,
    };
}

export function trackUxEvent(payload: UxTelemetryEventPayload): void {
    if (typeof window === 'undefined') return;
    void telemetryApi.logUxEvent(withPagePath(payload)).catch(() => undefined);
}

export function useTrackSurfaceView(surface: string, details?: UxDetails): void {
    const sentRef = useRef(false);

    useEffect(() => {
        if (sentRef.current) return;
        sentRef.current = true;
        trackUxEvent({
            event_name: 'surface_view',
            surface,
            details,
        });
    }, [surface, details]);
}

export function trackNextAction(surface: string, actionLabel: string, details?: UxDetails): void {
    trackUxEvent({
        event_name: 'next_action_click',
        surface,
        action_label: actionLabel,
        details,
    });
}

export function trackUiAction(surface: string, actionLabel: string, details?: UxDetails): void {
    trackUxEvent({
        event_name: 'ui_action',
        surface,
        action_label: actionLabel,
        details,
    });
}
