import {
  EllipsisIcon,
  InboxIcon,
  MailIcon,
  SmartphoneIcon,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import Link from "next/link";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notifications | Whistle",
};

function page() {
  const MOCK_NOTIFICATIONS = [
    {
      id: 1,
      message: "Welcome to the app!",
      read: false,
      userId: "cos3kdkm20akmcao34a",
      status: "PENDING",
      provider: "EMAIL",
    },
    {
      id: 2,
      message: "You have 5 new notifications",
      read: false,
      userId: "kdkmf210amdsc03msad",
      status: "PENDING",
      provider: "IN-APP",
    },
    {
      id: 3,
      message: "You're all caught up!",
      read: true,
      userId: "mvs92kaldncn38ajcnafs",
      status: "DELIVERED",
      provider: "IN-APP",
    },
    {
      id: 3,
      message: "You've got a new comment!",
      read: true,
      userId: "amdo2kavmc39cnavksfj",
      status: "DELIVERED",
      provider: "MOBILE",
    },
  ];

  const PROVIDER_ICONS: Record<string, JSX.Element> = {
    EMAIL: <MailIcon className="text-gray-500" size={15} />,
    MOBILE: <SmartphoneIcon className="text-gray-500" size={15} />,
    "IN-APP": <InboxIcon className="text-gray-500" size={15} />,
  };

  return (
    <div className="flex flex-col">
      <div className="w-full flex items-end justify-between">
        <div className="">
          <h1 className="text-xl font-medium mt-4">Notifications</h1>
          <p className="text-zinc-500 text-sm font-normal mt-2">
            View, manage, and send notifications
          </p>
        </div>
        <Button>Send Notification</Button>
      </div>
      <div className="w-full mt-8">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">ID</TableHead>
              <TableHead className="w-2/6">Message</TableHead>
              <TableHead className="">User ID</TableHead>
              <TableHead className="">Provider</TableHead>
              <TableHead className="">Status</TableHead>
              <TableHead className="text-right"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {MOCK_NOTIFICATIONS.map((notif) => (
              <TableRow key={notif.id}>
                <TableCell className="font-medium">{notif.id}</TableCell>
                <TableCell className="w-2/6">{notif.message}</TableCell>
                <TableCell>
                  <Link className="underline" href={`/users/${notif.userId}`}>
                    {notif.userId}
                  </Link>
                </TableCell>
                <TableCell className="flex items-center gap-2">
                  {PROVIDER_ICONS[notif.provider]}
                  {notif.provider[0] + notif.provider.slice(1).toLowerCase()}
                </TableCell>
                <TableCell>
                  {notif.status[0] + notif.status.slice(1).toLowerCase()}
                </TableCell>
                <TableCell className="text-right">
                  {/* dropdown menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <EllipsisIcon size={15} />
                    </DropdownMenuTrigger>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default page;
