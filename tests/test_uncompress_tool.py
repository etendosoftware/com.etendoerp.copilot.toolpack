import bz2
import gzip
import os
import shutil
import tarfile
import unittest
import zipfile

from tools.UncompressTool import UncompressTool


class TestUncompressTool(unittest.TestCase):
    def setUp(self):
        self.tool = UncompressTool()
        self.test_dir = './test_data'
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_test_file(self, file_name, content='This is a test file.'):
        file_path = os.path.join(self.test_dir, file_name)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path

    def create_zip_file(self):
        zip_path = os.path.join(self.test_dir, 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(self.create_test_file('test1.txt'), arcname='test1.txt')
            zipf.write(self.create_test_file('test2.txt'), arcname='test2.txt')
        return zip_path

    def create_tar_file(self):
        tar_path = os.path.join(self.test_dir, 'test.tar')
        with tarfile.open(tar_path, 'w') as tarf:
            tarf.add(self.create_test_file('test1.txt'), arcname='test1.txt')
            tarf.add(self.create_test_file('test2.txt'), arcname='test2.txt')
        return tar_path

    def create_gzip_file(self):
        gzip_path = os.path.join(self.test_dir, 'test.gz')
        with open(self.create_test_file('test.txt'), 'rb') as f_in:
            with gzip.open(gzip_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return gzip_path

    def create_bzip2_file(self):
        bzip2_path = os.path.join(self.test_dir, 'test.bz2')
        with open(self.create_test_file('test.txt'), 'rb') as f_in:
            with bz2.open(bzip2_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return bzip2_path

    def test_unzip(self):
        zip_path = self.create_zip_file()
        result = self.tool.run({'compressed_file_path': zip_path})
        self.assertIn('uncompressed_files_paths', result)
        self.assertEqual(len(result['uncompressed_files_paths']), 2)

    def test_ungzip(self):
        gzip_path = self.create_gzip_file()
        result = self.tool.run({'compressed_file_path': gzip_path})
        self.assertIn('uncompressed_files_paths', result)
        self.assertEqual(len(result['uncompressed_files_paths']), 1)

    def test_unbzip2(self):
        bzip2_path = self.create_bzip2_file()
        result = self.tool.run({'compressed_file_path': bzip2_path})
        self.assertIn('uncompressed_files_paths', result)
        self.assertEqual(len(result['uncompressed_files_paths']), 1)


if __name__ == '__main__':
    unittest.main()
