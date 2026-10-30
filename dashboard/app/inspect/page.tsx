/** The video inspection now lives on the review page. Kept so old links still work. */

import { redirect } from "next/navigation.js";

export default function InspectPage() {
  redirect("/#video-inspection");
}
