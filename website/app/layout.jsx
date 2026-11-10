import { Hind_Siliguri, Inter } from "next/font/google";
import "./globals.css";

const bangla = Hind_Siliguri({ subsets: ["bengali", "latin"], weight: ["400", "500", "600", "700"], variable: "--font-bn" });
const latin = Inter({ subsets: ["latin"], variable: "--font-en" });

export const metadata = {
  metadataBase: new URL("https://kothok.vercel.app"),
  title: "কথক · Kothok — অফলাইন বাংলা + English ভয়েস টাইপিং",
  description:
    "Windows-এর যেকোনো অ্যাপে শর্টকাট চেপে কথা বলুন, লেখা বসে যাবে। ১০০% অফলাইন, ফ্রি ও ওপেন সোর্স। Developed by rotexit.com",
  icons: { icon: "/favicon.ico", apple: "/logo.png" },
  openGraph: {
    title: "কথক · Kothok",
    description: "Offline Bangla + English voice typing for Windows — free & open source.",
    images: ["/og.png"],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
};

export default function RootLayout({ children }) {
  return (
    <html lang="bn" className={`${bangla.variable} ${latin.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
