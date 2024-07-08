"use client";
import MockInbox from "../../components/mock/MockInbox";
import { HeroHighlight, Highlight } from "../../components/ui/hero-highlight";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { BackgroundGradient } from "../../components/ui/background-gradient";
import ThemeToggle from "../../components/layout/ThemeToggle";

export default function Home() {
  return (
    <div suppressHydrationWarning className="">
      {/* <ThemeToggle /> */}
      <HeroHighlight className="flex items-center justify-between w-full flex-col lg:px-16 min-[1189px]:flex-row">
        <div className="flex flex-col w-min items-start text-3xl sm:text-5xl font-bold text-neutral-700 dark:text-white max-w-4xl leading-relaxed lg:leading-snug text-center">
          <div className="min-w-max">
            <p>The fastest way to build</p>
            <Highlight className="text-2xl sm:text-4xl text-black dark:text-white">
              in-app notifications with Next.js
            </Highlight>
          </div>
          <p className="text-base font-semibold mt-4 w-full">
            Whistle provides a simple yet powerful infrastructure to send, read,
            and monitor in-app notifications. We provide a REST API, a Next.js
            SDK, and prebuilt components to help you get started.
          </p>
          <div className="flex mt-4 gap-2 w-full">
            <Input
              className="bg-[#0f1011] border-[#2c2e33] font-normal placeholder:text-[#2c2e33]"
              type="email"
              placeholder="Email"
            />
            <Button>Join waitlist</Button>
          </div>
        </div>
        <div className="min-[1189px]:block hidden">
          <div className="flex flex-col items-center gap-4">
            <p className="text-2xl font-bold">{"<NotificationInbox />"}</p>
            <BackgroundGradient className="rounded-3xl max-w-min p-0 dark:bg-zinc-950 overflow-clip">
              <MockInbox />
            </BackgroundGradient>
          </div>
        </div>
      </HeroHighlight>
    </div>
  );
}
