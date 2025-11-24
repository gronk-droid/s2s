---
up:
  - "[[Bulk API Release]]"
tags:
  - "#project/work/dnsimple/release"
cssclasses:
  - centerHeaders
---

Using DNSimple's API, it has been easy to alter your DNS records using our endpoints.

Previously, if you wanted to alter multiple records, you had to make separate calls to the appropriate record endpoint.

Now, we have expanded the API to allow batch changes to DNS Zone Records.

If you want to create, delete, or update many records all at once, you can now do that with one call.

Let's take a quick look at how a call to this endpoint works:

Using curl, you'll pass the appropriate parameters for your auth, data type, as well as the json you are sending to the endpoint. Each type of operation has its own fields that are related to records.

If your POST request goes through, you'll get an HTTP 200 response along with a JSON of which records were changed.

All DNSimple customers can use the API to automate your DNS workflows. Learn more about it at developer.dnsimple.com.
