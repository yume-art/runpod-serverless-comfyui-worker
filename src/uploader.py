
from runpod.serverless.utils import rp_upload
import uuid
import os

# local modules: 
import utils 

def all_strings_start_with(strings, x='x'):
    # Use a generator expression to check if all strings start with 'x'
    return all(s.startswith(x) for s in strings)


def send_to_aws(base, output_files, bucket_folder='comfyui', bucket_creds = None):
    utils.log("attempting aws file upload...")

    if bucket_creds != None and not isinstance(bucket_creds, dict):
        utils.log(f"'bucket_creds' must be a JSON object")
        return (False, output_files)

    boto_client, transfer_config = rp_upload.get_boto_client(bucket_creds)
    if boto_client is None:
        utils.log("no aws credentials set in env, skipping aws upload!")
    else:
        bucket_urls = []
        for path in output_files:
            filepath = f"{base}/{path}"
            utils.log(f"uploading: {filepath}")
            aws_url = rp_upload.upload_file_to_bucket(
                file_name = path, # amazon filepath to copy to
                file_location = filepath, # local filepath to copy from
                bucket_name = bucket_folder, # aws bucket folder to put things in
                bucket_creds = bucket_creds, # override aws credentials per request - if given
            )
            #strip query params from url
            aws_url = aws_url.split('?')[0]
            bucket_urls.append(aws_url)
            
        # not uploaded so return regular filepaths
        if not all_strings_start_with(bucket_urls, 'local_upload/'):
            # return array of uploaded item's as: [presigned_url, presigned_url, ...]  
            utils.log("aws upload success! returning presigned urls")
            return (True, bucket_urls)

    # not uploaded so return regular filepaths
    utils.log("not uploaded to aws, returning local urls")
    return (False, output_files)
