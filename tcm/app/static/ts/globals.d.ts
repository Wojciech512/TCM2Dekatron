export {};

declare global {
  interface Window {
    TCMToast?: (
      message:
        | string
        | {
            message: string;
            type?: string;
            duration?: number;
          },
      options?: {
        type?: string;
        duration?: number;
      }
    ) => HTMLElement | null;
  }
}
