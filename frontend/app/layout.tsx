import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { Providers } from "@/components/shell/providers";
import { Sidebar } from "@/components/shell/sidebar";
import { TaskDrawer } from "@/components/task-drawer";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Goalpost",
  description: "A local-first planner where tasks are completed by evidence.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-wrap text-sm leading-normal">
        <Providers>
          <Sidebar />
          <main className="flex min-w-0 flex-[999_1_560px] flex-wrap content-start gap-8 px-10 pt-8 pb-12">
            {children}
          </main>
          <TaskDrawer />
        </Providers>
      </body>
    </html>
  );
}
