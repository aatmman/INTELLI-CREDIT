import { useEffect, useRef } from "react";

/**
 * LandingPage — renders the editorial landing page as a full-screen iframe
 * with all "Launch App" links pointing to /auth/login within the SPA.
 */
export default function LandingPage() {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const handleLoad = () => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;

        // Intercept all links/buttons that navigate to /auth/login
        doc.addEventListener("click", (e: MouseEvent) => {
          const target = e.target as HTMLElement;
          const anchor = target.closest("a[href='/auth/login']") as HTMLAnchorElement | null;
          const button = target.closest("button") as HTMLButtonElement | null;

          if (anchor) {
            e.preventDefault();
            window.location.href = "/auth/login";
          } else if (button) {
            const onclick = button.getAttribute("onclick") || "";
            if (onclick.includes("/auth/login")) {
              e.preventDefault();
              window.location.href = "/auth/login";
            }
          }
        });
      } catch {
        // cross-origin blocked — won't happen since same origin
      }
    };

    iframe.addEventListener("load", handleLoad);
    return () => iframe.removeEventListener("load", handleLoad);
  }, []);

  return (
    <iframe
      ref={iframeRef}
      src="/landing.html"
      title="Intelli-Credit"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        border: "none",
        margin: 0,
        padding: 0,
      }}
    />
  );
}
