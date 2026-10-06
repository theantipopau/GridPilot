import { SearchInput } from "../ui/Input";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  resultCount?: number;
  totalCount?: number;
}

/** Legacy adapter over `ui/SearchInput` - same props, one implementation.
 *  Local, client-side substring filtering; every list it serves is already
 *  fetched in full, so a server round-trip would only add latency. */
export default function SearchBox(props: Props) {
  return <SearchInput {...props} />;
}
