import { Avatar, AvatarFallback, AvatarImage } from "../ui/avatar";
import {
  AreaChartIcon,
  BellIcon,
  BlocksIcon,
  BuildingIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  Settings2Icon,
  UsersIcon,
  WebhookIcon,
} from "lucide-react";
import NavbarGroup from "./NavbarGroup";

function Navbar() {
  const NAV_GROUPS = [
    {
      title: "General",
      pages: [
        {
          title: "Dashboard",
          href: "/dashboard",
          icon: <LayoutDashboardIcon size={20} />,
        },
        {
          title: "Notifications",
          href: "/notifications",
          icon: <BellIcon size={20} />,
        },
        {
          title: "Users",
          href: "/users",
          icon: <UsersIcon size={20} />,
        },
        {
          title: "Customization",
          href: "/customization",
          icon: <Settings2Icon size={20} />,
        },
        {
          title: "Metrics",
          href: "/metrics",
          icon: <AreaChartIcon size={20} />,
          selected: true,
        },
      ],
    },
    {
      title: "Developers",
      pages: [
        {
          title: "Integrations",
          href: "/integrations",
          icon: <BlocksIcon size={20} />,
        },
        {
          title: "API Keys",
          href: "/api-keys",
          icon: <KeyRoundIcon size={20} />,
        },
        {
          title: "Webhooks",
          href: "/webhooks",
          icon: <WebhookIcon size={20} />,
        },
      ],
    },
  ];

  const BOT_NAV_GROUP = {
    title: "",
    pages: [
      {
        title: "Organization",
        href: "/team",
        icon: <BuildingIcon size={20} />,
      },
    ],
  };

  return (
    <div className="flex flex-col justify-between border-r w-1/6 px-2 py-4 h-full">
      <div className="flex flex-col gap-4">
        {NAV_GROUPS.map((group) => (
          <NavbarGroup group={group} key={group.title} />
        ))}
      </div>
      <div>
        <div className="border-t mb-4" />
        <NavbarGroup group={BOT_NAV_GROUP} />
      </div>
    </div>
  );
}

export default Navbar;
