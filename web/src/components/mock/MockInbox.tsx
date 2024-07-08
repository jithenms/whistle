import React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "../ui/avatar";
import { CircleAlert } from "lucide-react";

function MockInbox() {
  return (
    <div className="bg-white dark:border-slate-200 dark:text-black flex flex-col border min-w-max">
      <div className="flex px-4 pt-4 justify-between">
        <p className="font-semibold">Notifications</p>
        <p className="text-gray-500 text-sm">Mark all as read</p>
      </div>
      <div className="flex gap-36 dark:border-slate-200 border-t items-center justify-between bg-gray-100 mt-4 px-4 py-3">
        <div className="flex gap-2">
          <Avatar>
            <AvatarImage src="https://github.com/jithenms.png" />
            <AvatarFallback>JS</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-sm text-gray-500">
              <span className="font-semibold text-black">@jithenms</span> sent
              you a message
            </p>
            <p className="text-xs text-gray-600">28 mins ago</p>
          </div>
        </div>
        <div>
          <div className="w-2 h-2 bg-blue-500 rounded-full" />
        </div>
      </div>
      <div className="flex border-t dark:border-slate-200 items-center justify-between bg-gray-100 px-4 py-3">
        <div className="flex gap-2">
          <Avatar>
            <AvatarImage src="https://github.com/armans-code.png" />
            <AvatarFallback>AK</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-sm text-gray-500">
              <span className="font-semibold text-black">@armank</span> added
              you to{" "}
              <span className="font-semibold text-black">
                Designers Groupchat
              </span>
            </p>
            <p className="text-xs text-gray-600">2 hours ago</p>
          </div>
        </div>
        <div>
          <div className="w-2 h-2 bg-blue-500 rounded-full" />
        </div>
      </div>
      <div className="flex border-t dark:border-slate-200 items-center justify-between px-4 py-3 rounded-b-xl">
        <div className="flex gap-2">
          <div className="flex items-center justify-center h-10 w-10 overflow-hidden">
            <CircleAlert />
          </div>
          <div>
            <p className="text-sm text-gray-700">
              Your password has been changed
            </p>
            <p className="text-xs text-gray-600">7 hours ago</p>
          </div>
        </div>
      </div>
      <div className="flex border-t dark:border-slate-200 items-center justify-between px-4 py-3">
        <div className="flex gap-2">
          <Avatar>
            <AvatarImage src="https://github.com/person.png" />
            <AvatarFallback>PE</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-sm text-gray-500">
              <span className="font-semibold text-black">@person</span>{" "}
              mentioned you in a post
            </p>
            <p className="text-xs text-gray-600">Yesterday</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MockInbox;
