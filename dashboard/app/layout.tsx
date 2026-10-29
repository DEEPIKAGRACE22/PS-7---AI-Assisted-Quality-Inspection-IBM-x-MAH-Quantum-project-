/** Root layout. */

import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "PS-7 Inspection — Model results",
  description:
    "Evaluation results for every defect-detection and casting-classification model in the PS-7 quality inspection project.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
