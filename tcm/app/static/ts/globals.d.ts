export {};

declare global {
  interface TCMToastOptions {
    message?: string;
    type?: string;
    duration?: number;
  }

  type TCMToastInput = string | TCMToastOptions | null | undefined;

  interface Window {
    TCMToast?: (message: TCMToastInput, options?: TCMToastOptions) => HTMLElement | null;
  }
}
