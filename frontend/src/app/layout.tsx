import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Header from "../components/layout/Header";
import Navbar from "../components/layout/Navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Whistle Dashboard",
  description: "Manage and monitor notifications with Whistle",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // <ClerkProvider>
    <html lang="en">
      <body className={`${inter.className} h-screen`}>
        {/* <SignedOut>
            <SignInButton />
          </SignedOut>
          <SignedIn>
            <UserButton />
          </SignedIn> */}
        <div className="flex flex-col w-full h-full">
          <Header />
          <div className="flex h-full">
            <Navbar />
            <div className="w-full py-4 px-6">{children}</div>
          </div>
        </div>
      </body>
    </html>
    // </ClerkProvider>
  );
}
