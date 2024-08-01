import { Avatar, AvatarFallback, AvatarImage } from "../ui/avatar";

function Header() {
  return (
    <div className="w-full flex items-center justify-between border-b">
      {/* TODO: Make this our logo */}
      <h1 className="font-bold py-4 text-2xl text-center ml-4">Whistle</h1>
      {/* TODO: Make this a Clerk User Icon */}
      <Avatar className="mr-4">
        <AvatarImage src="https://github.com/armans-code.png" />
        <AvatarFallback>AK</AvatarFallback>
      </Avatar>
    </div>
  );
}

export default Header;
