/** Root layout. */

import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "SteelSight — Steel Surface Defect Inspection",
  description:
    "SteelSight: AI-powered steel surface defect inspection. Model evaluation, casting classification and video inspection for the PS-7 project review.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
