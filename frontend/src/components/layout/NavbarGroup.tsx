"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { ReactElement, ReactNode } from "react";

interface NavbarGroup {
  title: string;
  pages: {
    title: string;
    href: string;
    icon: ReactElement;
  }[];
}

function NavbarGroup({ group }: { group: NavbarGroup }) {
  const pathname = usePathname();
  return (
    <div key={group.title}>
      <p className="text-zinc-500 text-xs font-medium pl-4">{group.title}</p>
      <div className="flex flex-col gap-1 mt-2">
        {group.pages.map((page) => (
          <Link
            href={page.href}
            key={page.title}
            className={`w-full text-sm flex items-center gap-2 py-[0.40rem] px-4 rounded-md cursor-pointer ${
              pathname.startsWith(page.href)
                ? "text-black font-medium bg-gray-100"
                : "text-zinc-500 hover:text-black hover:bg-gray-100"
            }`}
          >
            <div className="">{page.icon}</div>
            <p>{page.title}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default NavbarGroup;
